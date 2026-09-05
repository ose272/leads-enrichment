"""Email drafter for generating personalized outreach emails for Shopify AI agents."""

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


# System prompt for the LLM - Shopify AI Agents
SHOPIFY_AI_AGENT_PROMPT = """You are writing a first-touch cold email to Shopify store owners pitching AI agents that run directly inside their Shopify store.

Product: AI Agents for Shopify that handle:
- Inventory tracking & automatic reorder alerts
- Customer support (AI chatbot handling 80%+ of tickets)
- Automated reports (sales, inventory, customer insights)
- Order management & fulfillment coordination

Key Differentiator: Final hand-off - we install it, you own it. No ongoing subscriptions, no vendor lock-in. The agents run in YOUR Shopify store, managed by YOUR team.

Given this lead info:
- Store: {store_name}
- Owner: {owner_name}
- Context: {context}

Write a SHORT (under 150 words) personalized cold email.

Requirements:
1. Reference their store specifically (name, niche if known)
2. Pitch the AI agents as installed directly in their Shopify store
3. Emphasize: "Final hand-off - your team manages it, no ongoing fees"
4. Mention 1-2 specific pain points (inventory stockouts, support overload, manual reporting)
5. End with a clear, low-friction call to action (reply "INTERESTED" or book 15-min call)
6. Avoid generic filler ("I hope this email finds you well", "I came across your store")
7. Professional but warm, founder-to-founder tone
8. No overclaiming - be specific about what the agents do

Output format:
SUBJECT: [subject line]
BODY: [email body]"""


# Fallback prompt when minimal info available
MINIMAL_PROMPT = """You are writing a cold email to a Shopify store owner pitching AI agents installed directly in their Shopify store.

The agents handle: inventory tracking, customer support automation, and automated reports.
Key selling point: Final hand-off - installed in their store, they own and manage it, no ongoing subscriptions.

Write a SHORT (under 150 words) email.

Requirements:
- Mention Shopify specifically
- Highlight "final hand-off / you own it" angle
- Reference inventory/support/reports pain points
- Clear CTA: reply INTERESTED or book quick call
- No generic filler
- Professional, founder-to-founder tone

Output format:
SUBJECT: [subject line]
BODY: [email body]"""


def draft_email(
    email: str,
    store_name: str = "",
    owner_name: str = "",
    context: str = "",
    paraphrase_seed: int = 0
) -> Optional[EmailDraft]:
    """Generate a personalized cold email for a Shopify store owner.
    
    Args:
        email: The lead's email address
        store_name: Their Shopify store name
        owner_name: Store owner's name (optional)
        context: Additional context about their business
        paraphrase_seed: Seed for generating paraphrased variations
        
    Returns:
        EmailDraft with subject and body, or None if generation fails
    """
    try:
        client = GroqClient()
        
        # Build context string
        context_parts = []
        if store_name:
            context_parts.append(f"Store: {store_name}")
        if owner_name:
            context_parts.append(f"Owner: {owner_name}")
        if context:
            context_parts.append(f"Notes: {context}")
        
        context_str = "\n".join(context_parts) if context_parts else "Shopify store owner"
        
        # Add paraphrase variation instruction
        variation_instruction = ""
        if paraphrase_seed > 0:
            variation_instruction = f"\n\nVARIATION: This is version #{paraphrase_seed}. Use different wording, angle, and structure than previous versions while keeping the same core pitch."
        
        prompt = SHOPIFY_AI_AGENT_PROMPT.format(
            store_name=store_name or "your store",
            owner_name=owner_name or "there",
            context=context_str
        ) + variation_instruction
        
        response = client.generate(prompt, max_tokens=400, temperature=0.8)
        
        # Parse subject and body from response
        subject = ""
        body = ""
        
        for line in response.split("\n"):
            if line.startswith("SUBJECT:"):
                subject = line[8:].strip()
            elif line.startswith("BODY:"):
                body = line[5:].strip()
            elif body and not subject:
                body += "\n" + line
        
        # Fallback parsing
        if not subject or not body:
            lines = response.strip().split("\n")
            if lines:
                subject = lines[0].replace("SUBJECT:", "").strip()
                body = "\n".join(lines[1:]).replace("BODY:", "").strip()
        
        if not subject:
            subject = f"AI agents for {store_name or 'your Shopify store'}"
        
        if not body:
            LOGGER.error("Failed to generate valid email body for %s", email)
            return None
        
        LOGGER.info("Generated draft for %s (%s): %s", email, store_name, subject[:50])
        return EmailDraft(subject=subject, body=body)
        
    except LLMCallError as e:
        LOGGER.error("LLM call failed for %s: %s", email, e)
        return None
    except Exception as e:
        LOGGER.error("Unexpected error drafting email for %s: %s", email, e)
        return None


def draft_followup(
    email: str,
    store_name: str,
    previous_subject: str,
    previous_body: str,
    followup_number: int,
    paraphrase_seed: int = 0
) -> Optional[EmailDraft]:
    """Generate a follow-up email for Shopify AI agent pitch.
    
    Args:
        email: Lead's email
        store_name: Store name
        previous_subject: Subject of previous email
        previous_body: Body of previous email
        followup_number: 1 or 2
        paraphrase_seed: Seed for variation
        
    Returns:
        EmailDraft or None
    """
    followup_prompt = f"""Write a SHORT follow-up email (under 80 words) for follow-up #{followup_number} to a Shopify store owner.

Previous email subject: {previous_subject}
Previous email body: {previous_body[:300]}

Context: We're pitching AI agents installed directly in their Shopify store that handle inventory, support, and reports - with final hand-off (they own it, no ongoing fees).

Requirements:
- Reference the earlier email briefly
- Keep it under 80 words
- Reinforce the "you own it, installed in your store" angle
- One clear call to action (reply INTERESTED or quick call)
- Professional, not pushy
- Different angle/wording from previous email

Output format:
SUBJECT: [subject line]
BODY: [email body]"""
    
    if paraphrase_seed > 0:
        followup_prompt += f"\n\nVARIATION: This is version #{paraphrase_seed}. Use fresh wording and angle."
    
    try:
        client = GroqClient()
        response = client.generate(followup_prompt, max_tokens=200, temperature=0.8)
        
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
        LOGGER.error("Failed to draft follow-up for %s: %s", email, e)
        return None
