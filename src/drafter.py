"""Email drafter for generating personalized outreach emails."""

from __future__ import annotations

import logging
import os
import re
import sys
from dataclasses import dataclass
from typing import Optional

if __package__ in (None, ""):
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from src.llm_client import GroqClient, LLMCallError

LOGGER = logging.getLogger("drafter")
SIGN_OFF = "Regards,\nStephen\nOSETEK ltd."
OUTREACH_SUBJECT = "YOU NEED TO HEAR THIS"
LEGACY_FOOTER_PATTERN = re.compile(
    r"\s*---\s*SE Global\s*\[Your Business Address\]\s*"
    r"\[Your City, State ZIP\]\s*"
    r"To unsubscribe, reply with [\"']UNSUBSCRIBE[\"'] in the subject line\.\s*",
    re.IGNORECASE,
)


def _whatsapp_link() -> str:
    value = (os.getenv("WHATSAPP_LINK") or os.getenv("WHATSAPP_NUMBER") or "").strip()
    if value.startswith(("http://", "https://")):
        value = value.rsplit("/", 1)[-1]
    digits = "".join(char for char in value if char.isdigit())
    if digits.startswith("0"):
        digits = f"234{digits[1:]}"
    return f"https://wa.me/{digits or '2349159313103'}"


def _fallback_subject(website: str) -> str:
    domain = website.replace("https://", "").replace("http://", "").split("/")[0]
    return OUTREACH_SUBJECT


def _fallback_email_body(website: str, business_context: str, followup_number: int = 0) -> str:
    domain = website.replace("https://", "").replace("http://", "").split("/")[0]
    context = (business_context or "your business").strip()
    if context and len(context) > 180:
        context = context[:180].rstrip() + "..."
    if followup_number > 0:
        return (
            f"Hi,\n\n"
            f"I wanted to follow up on my earlier note about helping {domain} handle more enquiries and repetitive tasks with AI. "
            f"If you're ready to explore it, message me on WhatsApp: {_whatsapp_link()}\n\n"
            f"{SIGN_OFF}"
        )
    return (
        f"Hi,\n\n"
        f"What if {domain} could handle more customers, enquiries, and repetitive tasks without constantly adding more staff?\n\n"
        f"AI can automate a large part of that workload, helping your business respond faster, operate more efficiently, and save valuable time.\n\n"
        f"If you're ready to transform your business with AI, message me on WhatsApp: {_whatsapp_link()}\n\n"
        f"{SIGN_OFF}"
    )


def _finalize_body(body: str) -> str:
    """Remove unresolved placeholders and enforce the operator's sign-off."""
    lines = body.strip().splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    if lines and re.match(r"(?i)^(hi|hello|dear)\s+\[[^\]]+\]\s*,?$", lines[0].strip()):
        lines[0] = "Hi,"
    body = "\n".join(lines).strip()
    body = re.sub(r"(?im)^\s*(best|best regards|kind regards|regards),?\s*$", "", body)
    body = re.sub(r"(?im)^\s*SE Global\s*$", "", body)
    body = re.sub(r"(?im)^\s*(Stephen|Stephen OSETEK|OSETEK ltd\.?)\s*$", "", body)
    body = re.sub(r"\[[^\]]+\]", "", body)
    body = LEGACY_FOOTER_PATTERN.sub("", body)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    return f"{body}\n\n{SIGN_OFF}"


@dataclass
class EmailDraft:
    """Container for email subject and body."""
    subject: str
    body: str


# System prompt for the LLM
DRAFT_PROMPT = """You are writing a first-touch cold email for OSETEK ltd., an AI automation company. Given this business context from a website:

{context}

Write a SHORT (under 150 words) email using the following foundation and adapt it naturally to the lead's business:

Hi,

What if your business could handle more customers, enquiries, and repetitive tasks without constantly adding more staff?

AI can automate a large part of that workload, helping your business respond faster, operate more efficiently, and save valuable time.

If you're ready to transform your business with AI, invite them to message you on WhatsApp: {whatsapp_link}

Requirements:
1. Identify the likely business type from the website content
2. Reference something SPECIFIC about their business where it fits, without inventing facts
3. Explain briefly how AI could help their type of business
4. Include a direct WhatsApp call to action
5. Avoid generic filler phrases like "I hope this email finds you well"
6. Professional but warm tone
7. No overclaiming results
8. If the recipient's first name is not explicitly provided, use "Hi," or "Hi there,". Never write "[name]", "[first name]", or any other placeholder.
9. End exactly with:
Regards,
Stephen
OSETEK ltd.

Output format:
SUBJECT: [subject line]
BODY: [email body]"""


def draft_email(website: str, business_context: str) -> Optional[EmailDraft]:
    """Generate a personalized cold email for a lead.
    
    Args:
        website: The lead's website URL
        business_context: Scraped content/summary from their website
        
    Returns:
        EmailDraft with subject and body, or None if generation fails
    """
    if not business_context or len(business_context.strip()) < 50:
        LOGGER.warning("Insufficient business context for %s, skipping draft", website)
        return None
    
    try:
        client = GroqClient()
        prompt = DRAFT_PROMPT.format(context=business_context[:2500], whatsapp_link=_whatsapp_link())
        response = client.generate(prompt, max_tokens=400, temperature=0.7)

        # Parse subject and body from response
        subject = ""
        body = ""

        for line in response.split("\n"):
            if line.startswith("SUBJECT:"):
                subject = line[8:].strip()
            elif line.startswith("BODY:"):
                body = line[5:].strip()
            elif body and not subject:
                # If BODY came first, continue accumulating
                body += "\n" + line

        # Fallback parsing if format not followed
        if not subject or not body:
            lines = response.strip().split("\n")
            if lines:
                subject = lines[0].replace("SUBJECT:", "").strip()
                body = "\n".join(lines[1:]).replace("BODY:", "").strip()

        if not subject:
            subject = _fallback_subject(website)

        if not body:
            LOGGER.error("Failed to generate valid email body for %s", website)
            return None

        LOGGER.info("Generated draft for %s: %s", website, subject[:50])
        return EmailDraft(subject=OUTREACH_SUBJECT, body=_finalize_body(body))

    except (LLMCallError, ValueError) as e:
        LOGGER.warning("LLM unavailable for %s; using fallback draft: %s", website, e)
        return EmailDraft(subject=_fallback_subject(website), body=_fallback_email_body(website, business_context, 0))
    except Exception as e:
        LOGGER.error("Unexpected error drafting email for %s: %s", website, e)
        return EmailDraft(subject=_fallback_subject(website), body=_fallback_email_body(website, business_context, 0))


def draft_followup(website: str, previous_subject: str, previous_body: str, followup_number: int) -> Optional[EmailDraft]:
    """Generate a follow-up email referencing the previous email.
    
    Args:
        website: The lead's website
        previous_subject: Subject of previous email
        previous_body: Body of previous email
        followup_number: 1 or 2
        
    Returns:
        EmailDraft or None
    """
    followup_prompt = f"""Write a SHORT follow-up email (under 80 words) for follow-up #{followup_number}.

Previous email subject: {previous_subject}
Previous email body: {previous_body[:300]}

Requirements:
- Reference the earlier email briefly
- Keep it under 80 words
- One clear call to action (reply if interested)
- Professional, not pushy
- No generic filler
- If no recipient name is explicitly provided, use "Hi," or "Hi there," and never use a name placeholder.
- End exactly with:
  Regards,
  Stephen
  OSETEK ltd.

Output format:
SUBJECT: [subject line]
BODY: [email body]"""
    
    try:
        client = GroqClient()
        response = client.generate(followup_prompt, max_tokens=200, temperature=0.7)

        subject = ""
        body = ""

        for line in response.split("\n"):
            if line.startswith("SUBJECT:"):
                subject = line[8:].strip()
            elif line.startswith("BODY:"):
                body = line[5:].strip()

        if not subject:
            subject = f"Re: {previous_subject}"

        if not body:
            return None

        return EmailDraft(subject=OUTREACH_SUBJECT, body=_finalize_body(body))

    except (ValueError, LLMCallError) as e:
        LOGGER.warning("LLM unavailable for follow-up on %s; using fallback: %s", website, e)
        return EmailDraft(
            subject=f"Re: {previous_subject or _fallback_subject(website)}",
            body=_fallback_email_body(website, previous_body or previous_subject, followup_number),
        )
    except Exception as e:
        LOGGER.error("Failed to draft follow-up for %s: %s", website, e)
        return EmailDraft(
            subject=f"Re: {previous_subject or _fallback_subject(website)}",
            body=_fallback_email_body(website, previous_body or previous_subject, followup_number),
        )
