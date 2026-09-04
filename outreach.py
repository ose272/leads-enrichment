"""Compliant SMTP outreach helpers with hard opt-out and handoff stops."""

from __future__ import annotations

import os
import re
import smtplib
import time
import uuid
from email.message import EmailMessage
from datetime import datetime, timezone
from typing import Any


OPTOUT_TERMS = ("stop", "unsubscribe", "not interested", "remove me", "do not contact")
HANDOFF_MESSAGE = "Great to hear it. Let's continue on WhatsApp so we can move faster: +234 915 931 3103."
OUTREACH_SIGN_OFF = "Regards,\nStephen\nOSETEK ltd."
OUTREACH_SUBJECT = "YOU NEED TO HEAR THIS"


def format_outreach_body(body: str) -> str:
    """Remove unresolved placeholders and enforce the operator's sign-off."""
    lines = (body or "").strip().splitlines()
    if lines and re.match(r"(?i)^(hi|hello|dear)\s+\[[^\]]+\]\s*,?$", lines[0].strip()):
        lines[0] = "Hi,"
    cleaned = "\n".join(lines).strip()
    cleaned = re.sub(r"(?im)^\s*(best|best regards|kind regards|regards),?\s*$", "", cleaned)
    cleaned = re.sub(r"(?im)^\s*(SE Global|Stephen|Stephen OSETEK|OSETEK ltd\.?)\s*$", "", cleaned)
    cleaned = re.sub(r"\[[^\]]+\]", "", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return f"{cleaned}\n\n{OUTREACH_SIGN_OFF}"


def contains_opt_out(message: str) -> bool:
    lowered = message.lower()
    return any(term in lowered for term in OPTOUT_TERMS)


class SmtpSender:
    def __init__(self, dry_run: bool = True, minimum_delay: float = 3.0, daily_cap: int | None = None) -> None:
        import os
        if daily_cap is None:
            daily_cap = int(os.getenv("DAILY_EMAIL_CAP", "30"))
        self.dry_run = dry_run
        self.minimum_delay = minimum_delay
        self.daily_cap = daily_cap
        self.sent_today = 0
        self.last_sent = 0.0

    def send(self, recipient: str, subject: str, body: str, in_reply_to: str | None = None) -> str:
        if self.sent_today >= self.daily_cap:
            raise RuntimeError("Daily SMTP send cap reached")
        delay = self.minimum_delay - (time.monotonic() - self.last_sent)
        if delay > 0:
            time.sleep(delay)
        message_id = f"<{uuid.uuid4()}@{os.getenv('SMTP_HOST', 'localhost')}>"
        message = EmailMessage()
        message["From"] = f"{os.getenv('SENDER_NAME', 'SE Global')} <{os.environ['SMTP_USER']}>"
        message["To"] = recipient
        message["Subject"] = OUTREACH_SUBJECT
        message["Message-ID"] = message_id
        if in_reply_to:
            message["In-Reply-To"] = in_reply_to
            message["References"] = in_reply_to
        message.set_content(format_outreach_body(body))
        if self.dry_run:
            print(f"DRY RUN: would send to {recipient}: {subject}")
        else:
            with smtplib.SMTP_SSL(os.environ["SMTP_HOST"], int(os.getenv("SMTP_PORT", "465"))) as server:
                server.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
                server.send_message(message)
        self.sent_today += 1
        self.last_sent = time.monotonic()
        return message_id
