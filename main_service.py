"""Main orchestration service for the SE Global Outreach Agent.

This module wires together all phases:
- Phase 2: Website enrichment & email scraping
- Phase 3: Initial outreach sending
- Phase 4: Reply polling and conversation handling
- Phase 5: Follow-up automation
- Phase 6: Weekly reporting
"""

from __future__ import annotations

import imaplib
import logging
import os
import signal
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler

from storage import LeadStore, Settings, load_env_file
from llm import Ollama
from outreach import SmtpSender, contains_opt_out, HANDOFF_MESSAGE, format_outreach_body
from pipeline import enrich_new_leads, classify_inbound, due_followup_status
from scraper import enrich_website

LOGGER = logging.getLogger("outreach_service")


class OutreachService:
    """Main service coordinating all outreach phases."""

    def __init__(self, settings: Settings, store: LeadStore, llm: Ollama, sender: SmtpSender) -> None:
        self.settings = settings
        self.store = store
        self.llm = llm
        self.sender = sender
        self.scheduler = BackgroundScheduler(timezone=timezone.utc)

    def start(self) -> None:
        """Start all scheduled jobs."""
        # Daily follow-up job (runs every hour to check for due follow-ups)
        self.scheduler.add_job(
            self.process_followups,
            "interval",
            hours=1,
            id="followups",
            max_instances=1,
            replace_existing=True,
        )

        # Weekly report job (runs every Sunday at 23:00 UTC)
        self.scheduler.add_job(
            self.send_weekly_report,
            "cron",
            day_of_week="sun",
            hour=23,
            minute=0,
            id="weekly_report",
            max_instances=1,
            replace_existing=True,
        )

        self.scheduler.start()
        LOGGER.info("Outreach service scheduled jobs started")

    def stop(self) -> None:
        """Stop all scheduled jobs."""
        self.scheduler.shutdown(wait=False)
        LOGGER.info("Outreach service stopped")

    def send_initial_outreach(self) -> int:
        """Phase 3: Send initial outreach emails to new leads with emails."""
        leads = self.store.get_leads_for_outreach()

        sent = 0
        for lead in leads:
            try:
                summary = lead["scraped_summary"] or f"Company: {lead['company'] or 'Unknown'}"
                pitch = format_outreach_body(self.llm.generate_pitch_email(summary))

                subject = f"AI automation for {lead['company'] or 'your business'}"
                if lead["first_name"]:
                    subject = f"Quick note for {lead['first_name']} at {lead['company'] or 'your company'}"

                thread_id = self.sender.send(lead["email"], subject, pitch)

                self.store.mark_emailed(lead["id"], thread_id)

                sent += 1
                LOGGER.info("Sent initial outreach to %s (lead %d)", lead["email"], lead["id"])

            except Exception as e:
                LOGGER.exception("Failed to send initial outreach to lead %d: %s", lead["id"], e)

        return sent

    def poll_replies(self) -> int:
        """Phase 4: Poll IMAP inbox for replies to our emails."""
        import imaplib
        import ssl
        import email
        from email import policy

        processed = 0

        try:
            client = imaplib.IMAP4_SSL(self.settings.imap_host, self.settings.imap_port, ssl_context=ssl.create_default_context())
            client.login(self.settings.imap_user, self.settings.imap_password)

            try:
                # Select inbox
                status, _ = client.select("INBOX")
                if status != "OK":
                    raise RuntimeError("Could not select INBOX")

                # Search for all messages
                status, data = client.uid("SEARCH", None, "ALL")
                if status != "OK":
                    raise RuntimeError("Could not search INBOX")

                for uid in (data[0] or b"").split():
                    status, fetched = client.uid("FETCH", uid, "(RFC822)")
                    if status != "OK" or not fetched or not fetched[0]:
                        continue

                    raw_message = fetched[0][1]
                    message = email.message_from_bytes(raw_message, policy=policy.default)

                    # Check if this is a reply to one of our emails
                    in_reply_to = message.get("In-Reply-To") or message.get("References")
                    if not in_reply_to:
                        continue

                    # Find matching lead by thread_id
                    lead = self.store.connection.execute(
                        "SELECT id, email, status FROM leads WHERE thread_id = ?", (in_reply_to.strip(),)
                    ).fetchone()

                    if not lead:
                        continue

                    # Skip if already handed off or unsubscribed
                    if lead["status"] in ("handed_off", "unsubscribed", "archived_no_response"):
                        continue

                    # Extract message body
                    body = self._extract_body(message)
                    if not body:
                        continue

                    # Process the reply
                    new_status = classify_inbound(self.store, lead["id"], body, self.llm)

                    # Handle handoff - send WhatsApp number
                    if new_status == "handed_off":
                        self._send_handoff_reply(lead, in_reply_to.strip())

                    # Handle other intents - generate and send reply
                    elif new_status in ("curious", "objecting", "neutral"):
                        self._send_ai_reply(lead, body, in_reply_to.strip())

                    processed += 1
                    LOGGER.info("Processed reply from %s (lead %d) -> %s", lead["email"], lead["id"], new_status)

            finally:
                client.logout()

        except Exception as e:
            LOGGER.exception("Reply polling failed: %s", e)

        return processed

    def _extract_body(self, message: email.message.EmailMessage) -> str:
        """Extract text body from email message."""
        body_parts = []
        if message.is_multipart():
            for part in message.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        body_parts.append(payload.decode(errors="ignore"))
        else:
            payload = message.get_payload(decode=True)
            if payload:
                body_parts.append(payload.decode(errors="ignore"))
        return "\n".join(body_parts).strip()

    def _send_handoff_reply(self, lead: Any, in_reply_to: str) -> None:
        """Send handoff message with WhatsApp number."""
        try:
            self.sender.send(
                recipient=lead["email"],
                subject="",
                body=HANDOFF_MESSAGE,
                in_reply_to=in_reply_to,
            )
            with self.store.connection:
                self.store.connection.execute(
                    "INSERT INTO conversation_log (lead_id, direction, message, timestamp) VALUES (?, 'outbound', ?, ?)",
                    (lead["id"], HANDOFF_MESSAGE, datetime.now(timezone.utc).isoformat()),
                )
        except Exception as e:
            LOGGER.exception("Failed to send handoff reply to lead %d: %s", lead["id"], e)

    def _send_ai_reply(self, lead: Any, inbound_message: str, in_reply_to: str) -> None:
        """Generate and send AI reply to lead."""
        try:
            reply = self.llm.generate_followup_reply(inbound_message)
            self.sender.send(
                recipient=lead["email"],
                subject="",
                body=reply,
                in_reply_to=in_reply_to,
            )
            with self.store.connection:
                self.store.connection.execute(
                    "INSERT INTO conversation_log (lead_id, direction, message, timestamp) VALUES (?, 'outbound', ?, ?)",
                    (lead["id"], reply, datetime.now(timezone.utc).isoformat()),
                )
        except Exception as e:
            LOGGER.exception("Failed to send AI reply to lead %d: %s", lead["id"], e)

    def process_followups(self) -> int:
        """Phase 5: Send follow-up emails to leads that haven't replied."""
        leads = self.store.get_due_followups()

        processed = 0
        for lead in leads:
            next_status = due_followup_status(lead["last_contacted_at"], lead["followup_count"])
            if not next_status:
                continue

            try:
                summary = lead["scraped_summary"] or f"Company: {lead['company'] or 'Unknown'}"

                if next_status == "followup_1":
                    pitch = self.llm.generate(
                        f"Write a brief, polite follow-up email (under 100 words) for SE Global. "
                        f"We previously pitched AI automation to {lead['company'] or 'this business'}. "
                        f"Business context: {summary}. No pressure, just checking in. One clear CTA to reply."
                    )
                elif next_status == "followup_2":
                    pitch = self.llm.generate(
                        f"Write a final follow-up email (under 80 words) for SE Global. "
                        f"This is our last outreach to {lead['company'] or 'this business'}. "
                        f"Business context: {summary}. Warm, low-pressure, leave the door open."
                    )
                else:  # archived_no_response
                    with self.store.connection:
                        self.store.connection.execute(
                            "UPDATE leads SET status = 'archived_no_response' WHERE id = ?",
                            (lead["id"],),
                        )
                    LOGGER.info("Archived lead %d (no response after follow-ups)", lead["id"])
                    continue

                thread_id = self.sender.send(
                    recipient=lead["email"],
                    subject=f"Following up: AI automation for {lead['company'] or 'your business'}",
                    body=pitch,
                    in_reply_to=lead["thread_id"],
                )

                self.store.mark_followup_sent(lead["id"], lead["followup_count"] + 1, thread_id)

                processed += 1
                LOGGER.info("Sent %s to %s (lead %d)", next_status, lead["email"], lead["id"])

            except Exception as e:
                LOGGER.exception("Failed to send follow-up to lead %d: %s", lead["id"], e)

        return processed

    def send_weekly_report(self) -> None:
        """Phase 6: Generate and send weekly performance report."""
        try:
            # Gather stats from the past week using the new store method
            week_ago = datetime.now(timezone.utc) - timedelta(days=7)
            stats = self.store.get_weekly_stats(week_ago)

            # Generate report using LLM
            stats_text = "\n".join([f"{k}: {v}" for k, v in stats.items() if k != "top_companies"])
            if stats["top_companies"]:
                stats_text += "\nTop companies by replies:\n" + "\n".join([f"  {r['company']}: {r['replies']}" for r in stats["top_companies"]])

            report = self.llm.generate_weekly_report(stats_text)

            # Email report to sender
            self.sender.send(
                recipient=os.environ["SMTP_USER"],
                subject="SE Global Weekly Outreach Report",
                body=report,
            )

            LOGGER.info("Weekly report sent")

        except Exception as e:
            LOGGER.exception("Failed to generate/send weekly report: %s", e)

    def run_cycle(self) -> None:
        """Run one complete cycle of all phases."""
        LOGGER.info("Starting outreach cycle")
        
        # Phase 2: Enrich new leads
        enriched = enrich_new_leads(self.store)
        if enriched:
            LOGGER.info("Enriched %d new leads", enriched)
        
        # Phase 3: Send initial outreach
        sent = self.send_initial_outreach()
        if sent:
            LOGGER.info("Sent %d initial outreach emails", sent)
        
        # Phase 4: Poll for replies
        replies = self.poll_replies()
        if replies:
            LOGGER.info("Processed %d replies", replies)
        
        # Phase 5: Process follow-ups
        followups = self.process_followups()
        if followups:
            LOGGER.info("Processed %d follow-ups", followups)
        
        LOGGER.info("Outreach cycle complete")


def run_foreground(settings: Settings) -> None:
    """Run the service in foreground mode with scheduled jobs."""
    load_env_file()
    
    store = LeadStore(settings.database_path)
    llm = Ollama(os.getenv("OLLAMA_MODEL", "llama3.1:8b"))
    sender = SmtpSender(
        dry_run=os.getenv("DRY_RUN", "true").lower() == "true",
        minimum_delay=3.0,
        daily_cap=int(os.getenv("DAILY_EMAIL_CAP", "30")),
    )
    
    service = OutreachService(settings, store, llm, sender)
    
    def signal_handler(signum, frame):
        LOGGER.info("Shutdown signal received")
        service.stop()
        store.close()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    service.start()
    
    # Run initial cycle
    service.run_cycle()
    
    # Keep running and let scheduler handle recurring jobs
    LOGGER.info("Service running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(60)
            # Run cycle every 10 minutes
            service.run_cycle()
    except KeyboardInterrupt:
        pass
    finally:
        service.stop()
        store.close()


if __name__ == "__main__":
    load_env_file()
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s")
    
    settings = Settings.from_env()
    run_foreground(settings)