"""Phase 2-6 orchestration primitives."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from llm import Ollama
from outreach import HANDOFF_MESSAGE, contains_opt_out
from scraper import enrich_website


def enrich_new_leads(store: Any) -> int:
    leads = store.connection.execute("SELECT id, website, email FROM leads WHERE status = 'new'").fetchall()
    count = 0
    for lead in leads:
        summary, emails = enrich_website(lead["website"] if "website" in lead.keys() else "")
        had_email = bool(lead["email"] and lead["email"].strip())
        found_email = emails[0] if emails else None
        
        with store.connection:
            if found_email:
                # Found email on website - use it
                store.connection.execute(
                    "UPDATE leads SET email = ?, scraped_summary = ?, status = 'new' WHERE id = ?",
                    (found_email, summary, lead["id"])
                )
            elif had_email:
                # Already had email from CSV - keep it, don't mark as no_email_found
                store.connection.execute(
                    "UPDATE leads SET scraped_summary = ? WHERE id = ?",
                    (summary, lead["id"])
                )
            else:
                # No email from CSV and none found on website
                store.connection.execute(
                    "UPDATE leads SET scraped_summary = ?, status = 'no_email_found' WHERE id = ?",
                    (summary, lead["id"])
                )
        count += 1
    return count


def classify_inbound(store: Any, lead_id: int, message: str, llm: Ollama) -> str:
    if contains_opt_out(message):
        status = "unsubscribed"
    else:
        status = llm.classify_reply_intent(message)
        if status == "ready-to-talk":
            status = "handed_off"
    with store.connection:
        store.connection.execute("INSERT INTO conversation_log (lead_id, direction, message, timestamp) VALUES (?, 'inbound', ?, ?)", (lead_id, message, datetime.now(timezone.utc).isoformat()))
        store.connection.execute("UPDATE leads SET status = ? WHERE id = ?", (status, lead_id))
    return status


def due_followup_status(last_contacted_at: str | None, followup_count: int, now: datetime | None = None) -> str | None:
    if not last_contacted_at:
        return None
    current = now or datetime.now(timezone.utc)
    contacted = datetime.fromisoformat(last_contacted_at)
    age = current - contacted
    if followup_count == 0 and age >= timedelta(days=2):
        return "followup_1"
    if followup_count == 1 and age >= timedelta(days=2):
        return "followup_2"
    if followup_count == 2 and age >= timedelta(hours=24):
        return "archived_no_response"
    return None
