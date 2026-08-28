"""Email drafter for generating personalized outreach emails."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from src.llm_client import GroqClient, LLMCallError

LOGGER = logging.getLogger("drafter")


@dataclass
class EmailDraft:
    """Container for email subject and body."""
    subject: str
    body: str


# System prompt for the LLM
DRAFT_PROMPT = """You are writing a first-touch cold email for an AI automation company. Given this business context from a website:

{context}

Write a SHORT (under 150 words) personalized cold email pitching AI workflow/automation integration.

Requirements:
1. Identify the likely business type from the website content
2. Reference something SPECIFIC about their business (not generic)
3. Pitch how AI automation could specifically help THEIR type of business
4. End with a clear call to action (reply to this email)
5. Avoid generic filler phrases like "I hope this email finds you well"
6. Professional but warm tone
7. No overclaiming results

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
        prompt = DRAFT_PROMPT.format(context=business_context[:2500])
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
            subject = f"AI automation for {website.replace('https://', '').replace('http://', '').split('/')[0]}"
        
        if not body:
            LOGGER.error("Failed to generate valid email body for %s", website)
            return None
        
        LOGGER.info("Generated draft for %s: %s", website, subject[:50])
        return EmailDraft(subject=subject, body=body)
        
    except LLMCallError as e:
        LOGGER.error("LLM call failed for %s: %s", website, e)
        return None
    except Exception as e:
        LOGGER.error("Unexpected error drafting email for %s: %s", website, e)
        return None


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
            
        return EmailDraft(subject=subject, body=body)
        
    except Exception as e:
        LOGGER.error("Failed to draft follow-up for %s: %s", website, e)
        return None
