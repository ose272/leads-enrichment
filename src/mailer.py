"""Email sender and reply checker for the Outreach Agent."""

from __future__ import annotations

import logging
import os
import re
import smtplib
import ssl
import sys
from email.message import EmailMessage

from imapclient import IMAPClient

if __package__ in (None, ""):
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from src.tracker import LeadStore

LOGGER = logging.getLogger("mailer")


def get_whatsapp_link() -> str:
    """Return the WhatsApp handoff link configured for the operator."""
    raw_value = (os.getenv("WHATSAPP_LINK") or os.getenv("WHATSAPP_NUMBER") or "").strip()
    if not raw_value:
        return "https://wa.me/15551234567"
    if raw_value.startswith("http://") or raw_value.startswith("https://"):
        raw_value = raw_value.rsplit("/", 1)[-1]
    digits = "".join(ch for ch in raw_value if ch.isdigit() or ch in "+")
    if not digits:
        return "https://wa.me/15551234567"
    if digits.startswith("+"):
        return f"https://wa.me/{digits[1:]}"
    if digits.startswith("0"):
        return f"https://wa.me/234{digits[1:]}"
    return f"https://wa.me/{digits}"


OUTREACH_SUBJECT = "YOU NEED TO HEAR THIS"
LEGACY_FOOTER_PATTERN = re.compile(
    r"\s*---\s*SE Global\s*\[Your Business Address\]\s*"
    r"\[Your City, State ZIP\]\s*"
    r"To unsubscribe, reply with [\"']UNSUBSCRIBE[\"'] in the subject line\.\s*",
    re.IGNORECASE,
)


class EmailSender:
    """Handles sending emails via SMTP."""

    def __init__(
        self,
        smtp_host: str = None,
        smtp_port: int = None,
        smtp_user: str = None,
        smtp_password: str = None,
        sender_name: str = None,
        dry_run: bool = False,
    ):
        self.smtp_host = smtp_host or os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = smtp_port or int(os.getenv("SMTP_PORT", "465"))
        self.smtp_user = smtp_user or os.getenv("SMTP_USER")
        self.smtp_password = smtp_password or os.getenv("SMTP_PASSWORD")
        self.sender_name = sender_name or os.getenv("SENDER_NAME", "SE Global")
        self.dry_run = dry_run or os.getenv("DRY_RUN", "true").lower() == "true"

        if not self.dry_run and (not self.smtp_user or not self.smtp_password):
            raise ValueError("SMTP credentials not configured")

    def send_email(self, to_address: str, subject: str, body: str) -> bool:
        """Send an email via SMTP."""
        body = LEGACY_FOOTER_PATTERN.sub("", body or "").strip()
        msg = EmailMessage()
        msg["From"] = f"{self.sender_name} <{self.smtp_user}>" if self.smtp_user else self.sender_name
        msg["To"] = to_address
        msg["Subject"] = OUTREACH_SUBJECT
        msg.set_content(body)

        if self.dry_run:
            LOGGER.info("[DRY RUN] Would send email to %s: %s", to_address, subject)
            return True

        try:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, context=context) as server:
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            LOGGER.info("Sent email to %s: %s", to_address, subject)
            return True
        except smtplib.SMTPAuthenticationError:
            LOGGER.error("SMTP authentication failed - check credentials")
            return False
        except smtplib.SMTPRecipientsRefused:
            LOGGER.error("Recipient refused: %s", to_address)
            return False
        except Exception as exc:
            LOGGER.error("Failed to send email to %s: %s", to_address, exc)
            return False


class ReplyChecker:
    """Checks for replies to sent emails via IMAP."""

    def __init__(
        self,
        imap_host: str = None,
        imap_port: int = None,
        imap_user: str = None,
        imap_password: str = None,
        store: LeadStore = None,
    ):
        self.imap_host = imap_host or os.getenv("IMAP_HOST", "imap.gmail.com")
        self.imap_port = imap_port or int(os.getenv("IMAP_PORT", "993"))
        self.imap_user = imap_user or os.getenv("IMAP_USER")
        self.imap_password = imap_password or os.getenv("IMAP_PASSWORD")
        self.store = store
        self.llm_client = None

        if self.imap_user and self.imap_password:
            try:
                from src.llm_client import GroqClient

                self.llm_client = GroqClient()
            except Exception as exc:
                LOGGER.warning("Groq client unavailable for reply classification: %s", exc)

    def check_replies(self) -> int:
        """Poll IMAP inbox for new replies to our sent emails."""
        if not self.store:
            LOGGER.warning("No LeadStore provided, cannot check replies")
            return 0
        if not self.imap_user or not self.imap_password:
            LOGGER.info("IMAP credentials unavailable; skipping reply polling")
            return 0

        processed = 0
        try:
            with IMAPClient(self.imap_host, port=self.imap_port, ssl=True) as client:
                client.login(self.imap_user, self.imap_password)
                client.select_folder("INBOX")

                all_leads = []
                for status in ["sent", "replied", "follow_up_1", "follow_up_2"]:
                    leads = self.store.get_leads_by_status(status)
                    all_leads.extend(leads)

                if not all_leads:
                    return 0

                lead_emails = [lead.contact_email for lead in all_leads if lead.contact_email]
                if not lead_emails:
                    return 0

                for email_addr in lead_emails:
                    messages = client.search(["FROM", email_addr, "UNSEEN"])
                    for msg_id in messages:
                        processed += 1
                        self._process_reply(client, msg_id, email_addr)

        except Exception as exc:
            LOGGER.error("Error checking replies: %s", exc)

        return processed

    def _process_reply(self, client: IMAPClient, msg_id: int, from_email: str) -> None:
        """Process a single reply email."""
        leads = self.store.get_leads_by_email(from_email)
        if not leads:
            LOGGER.warning("No lead found for email: %s", from_email)
            return

        lead = leads[0]
        msg_data = client.fetch(msg_id, ["RFC822"])
        raw_email = msg_data[msg_id][b"RFC822"]

        import email

        msg = email.message_from_bytes(raw_email)

        reply_text = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    reply_text = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                    break
        else:
            reply_text = msg.get_payload(decode=True).decode("utf-8", errors="ignore")

        sentiment = self._classify_sentiment(reply_text)
        LOGGER.info("Reply from %s classified as: %s", from_email, sentiment)

        if sentiment == "positive":
            self.store.update_lead(
                lead.id,
                status="replied",
                last_reply=reply_text,
                follow_up_date=None,
            )
            self._send_handoff(lead)
        elif sentiment == "negative":
            self.store.update_lead(
                lead.id,
                status="closed",
                last_reply=reply_text,
                follow_up_date=None,
            )
        else:
            self.store.update_lead(lead.id, status="replied", last_reply=reply_text)

        client.add_flags(msg_id, ["\\Seen"])

    def _classify_sentiment(self, reply_text: str) -> str:
        """Classify reply sentiment using LLM."""
        if not self.llm_client:
            LOGGER.info("No LLM configured for reply sentiment classification; defaulting to neutral")
            return "neutral"

        prompt = f"""Classify this email reply as exactly ONE of: positive, neutral, negative.

Reply: {reply_text[:1000]}

Respond with only one word: positive, neutral, or negative."""

        try:
            result = self.llm_client.generate(prompt, max_tokens=10, temperature=0.1)
            result = result.strip().lower()

            if "positive" in result:
                return "positive"
            if "negative" in result:
                return "negative"
            return "neutral"
        except Exception as exc:
            LOGGER.warning("Sentiment classification failed: %s", exc)
            return "neutral"

    def _send_handoff(self, lead) -> None:
        """Send WhatsApp handoff email for positive replies."""
        whatsapp_link = get_whatsapp_link()
        handoff_body = f"""Hi there,

Thanks for your interest! I'd love to chat more about how AI automation can help your business.

Let's connect on WhatsApp: {whatsapp_link}

Looking forward to it!

Best regards,
SE Global"""

        sender = EmailSender()
        sender.send_email(
            lead.contact_email,
            "Next steps - Let's connect on WhatsApp",
            handoff_body,
        )
        LOGGER.info("Sent WhatsApp handoff to lead %d", lead.id)


def send_email(to_address: str, subject: str, body: str) -> bool:
    """Convenience function to send an email."""
    sender = EmailSender()
    return sender.send_email(to_address, subject, body)


def check_replies(store: LeadStore) -> int:
    """Convenience function to check for replies."""
    checker = ReplyChecker(store=store)
    return checker.check_replies()
