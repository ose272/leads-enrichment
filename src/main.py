"""Main orchestration module for the Outreach Agent (Shopify AI Agents).

Modes:
- --mode daily: Run daily outreach cycle (draft, send, check replies, follow-ups)
- --mode report: Generate weekly report
- --mode draft: Only draft emails for new leads
- --mode send: Only send drafted emails
- --mode upload: Upload CSV of Shopify store owners (with emails)
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Optional

from dotenv import load_dotenv

from src.tracker import LeadStore
from src.drafter import draft_email, draft_followup
from src.mailer import send_email, check_replies
from src.reporter import run_weekly_report

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s"
)

LOGGER = logging.getLogger("main")


def load_csv(filepath: str, store: LeadStore) -> int:
    """Load Shopify store owners from CSV and add to leads table.
    
    Expected CSV columns:
    - email (required): Store owner's email
    - store_name (optional): Shopify store name
    - owner_name (optional): Store owner's name
    - website (optional): Store URL
    - context (optional): Additional notes/context
    - paraphrase_seed (optional): Seed for email variation (default 0)
    
    Args:
        filepath: Path to CSV file
        store: LeadStore instance
        
    Returns:
        Number of new leads added
    """
    import pandas as pd
    
    if not os.path.exists(filepath):
        LOGGER.error("CSV file not found: %s", filepath)
        return 0
    
    df = pd.read_csv(filepath)
    
    if "email" not in df.columns:
        LOGGER.error("CSV must have an 'email' column")
        return 0
    
    # Clean data
    df = df.dropna(subset=["email"])
    df["email"] = df["email"].astype(str).str.strip().str.lower()
    df = df[df["email"] != ""]
    df = df.drop_duplicates(subset=["email"])
    
    added = 0
    for _, row in df.iterrows():
        try:
            email = row["email"]
            store_name = str(row.get("store_name", "")).strip() if pd.notna(row.get("store_name")) else ""
            owner_name = str(row.get("owner_name", "")).strip() if pd.notna(row.get("owner_name")) else ""
            website = str(row.get("website", "")).strip() if pd.notna(row.get("website")) else ""
            context = str(row.get("context", "")).strip() if pd.notna(row.get("context")) else ""
            paraphrase_seed = int(row.get("paraphrase_seed", 0)) if pd.notna(row.get("paraphrase_seed")) else 0
            
            # Normalize website
            if website and not website.startswith(("http://", "https://")):
                website = "https://" + website
            
            lead_id = store.add_lead(
                website=website or f"shopify-{email.split('@')[0]}",
                contact_email=email,
                store_name=store_name,
                owner_name=owner_name,
                paraphrase_seed=paraphrase_seed
            )
            if lead_id:
                added += 1
                LOGGER.info("Added lead: %s (%s)", email, store_name)
        except Exception as e:
            LOGGER.warning("Failed to add %s: %s", row.get("email", "unknown"), e)
    
    LOGGER.info("Loaded CSV: %d new leads added from %d unique emails", added, len(df))
    return added


def run_draft_phase(store: LeadStore) -> int:
    """Draft emails for leads with status 'new' that have emails.
    
    Returns:
        Number of emails drafted
    """
    leads = store.get_leads_by_status("new")
    drafted = 0
    
    for lead in leads:
        if not lead.contact_email:
            LOGGER.info("Skipping lead %d - no email", lead.id)
            continue
            
        LOGGER.info("Drafting email for %s (%s)", lead.store_name or lead.contact_email, lead.contact_email)
        
        try:
            # Build context from available info
            context_parts = []
            if lead.store_name:
                context_parts.append(f"Store: {lead.store_name}")
            if lead.owner_name:
                context_parts.append(f"Owner: {lead.owner_name}")
            if lead.notes:
                context_parts.append(f"Notes: {lead.notes}")
            context = "\n".join(context_parts)
            
            # Use paraphrase_seed from lead for variation
            paraphrase_seed = getattr(lead, 'paraphrase_seed', 0) or 0
            
            draft = draft_email(
                email=lead.contact_email,
                store_name=lead.store_name,
                owner_name=lead.owner_name,
                context=context,
                paraphrase_seed=paraphrase_seed
            )
            
            if draft:
                store.update_status(
                    lead.id, "drafted", 
                    email_subject=draft.subject, 
                    email_body=draft.body
                )
                drafted += 1
                LOGGER.info("Drafted email for %s: %s", lead.contact_email, draft.subject[:50])
            else:
                LOGGER.warning("Failed to draft email for %s", lead.contact_email)
                
        except Exception as e:
            LOGGER.error("Error drafting email for %s: %s", lead.contact_email, e)
    
    return drafted


def run_send_phase(store: LeadStore) -> int:
    """Send emails for leads with status 'drafted'.
    
    Returns:
        Number of emails sent
    """
    leads = store.get_leads_by_status("drafted")
    sent = 0
    
    for lead in leads:
        if not lead.contact_email:
            LOGGER.warning("Lead %d has no contact email", lead.id)
            continue
            
        if not lead.last_email_subject or not lead.last_email_body:
            LOGGER.warning("Lead %d missing draft content", lead.id)
            continue
        
        LOGGER.info("Sending email to %s", lead.contact_email)
        
        try:
            success = send_email(lead.contact_email, lead.last_email_subject, lead.last_email_body)
            if success:
                store.update_status(
                    lead.id, "sent", 
                    email_subject=lead.last_email_subject, 
                    email_body=lead.last_email_body
                )
                sent += 1
                LOGGER.info("Sent email to %s", lead.contact_email)
            else:
                LOGGER.error("Failed to send email to %s", lead.contact_email)
                
        except Exception as e:
            LOGGER.error("Error sending email to %s: %s", lead.contact_email, e)
    
    return sent


def run_reply_phase(store: LeadStore) -> int:
    """Check for replies and update lead statuses.

    Returns:
        Number of replies processed
    """
    return check_replies(store)


def run_followup_phase(store: LeadStore) -> int:
    """Send follow-ups to leads that haven't replied.
    
    Returns:
        Number of follow-ups sent
    """
    # Get leads in 'sent' or 'follow_up_1' status older than 2 days with no reply
    leads = store.get_leads_for_followup(days=2)
    sent = 0
    
    for lead in leads:
        if not lead.contact_email:
            continue
            
        # Determine follow-up number (1 or 2)
        followup_number = lead.follow_up_count + 1
        
        LOGGER.info("Sending follow-up #%d to %s (%s)", followup_number, lead.contact_email, lead.store_name)
        
        try:
            # Use stored email subject/body for reference
            previous_subject = lead.last_email_subject or ""
            previous_body = lead.last_email_body or ""
            
            paraphrase_seed = getattr(lead, 'paraphrase_seed', 0) or 0
            
            followup = draft_followup(
                email=lead.contact_email,
                store_name=lead.store_name,
                previous_subject=previous_subject,
                previous_body=previous_body,
                followup_number=followup_number,
                paraphrase_seed=paraphrase_seed
            )
            
            if followup:
                success = send_email(lead.contact_email, followup.subject, followup.body)
                if success:
                    # Update status to follow_up_1 or follow_up_2
                    new_status = "follow_up_1" if followup_number == 1 else "follow_up_2"
                    store.update_status(lead.id, new_status, email_subject=followup.subject, email_body=followup.body)
                    sent += 1
                    LOGGER.info("Sent follow-up #%d to %s", followup_number, lead.contact_email)
                else:
                    LOGGER.error("Failed to send follow-up #%d to %s", followup_number, lead.contact_email)
            else:
                LOGGER.warning("Failed to draft follow-up #%d for lead %d", followup_number, lead.id)
                
        except Exception as e:
            LOGGER.error("Error sending follow-up #%d to %s: %s", followup_number, lead.contact_email, e)
    
    return sent
    
    return sent

def run_report_phase(store: LeadStore) -> int:
    """Generate weekly report.

    Returns:
        Number of leads in report
    """
    run_weekly_report(store)
    # Return count of leads in the report
    leads = store.get_leads_by_status("replied")
    return len(leads)

def run_daily_cycle(store: LeadStore) -> dict[str, int]:
    """Run the complete daily outreach cycle.
    
    Returns:
        Dictionary with counts for each phase
    """
    LOGGER.info("Starting daily outreach cycle")
    
    results = {}
    
    # Phase 1: Draft emails for new leads
    results["drafted"] = run_draft_phase(store)
    
    # Phase 2: Send emails
    results["sent"] = run_send_phase(store)
    
    # Phase 3: Check replies
    results["replies_processed"] = check_replies(store)
    
    # Phase 4: Send follow-ups
    results["followups_sent"] = run_followup_phase(store)
    
    LOGGER.info("Daily cycle complete: %s", results)
    return results


def main():
    """Main entry point with command-line argument parsing."""
    parser = argparse.ArgumentParser(description="Outreach Agent - Shopify AI Agents Outreach")
    parser.add_argument("--mode", choices=["daily", "report", "draft", "send", "upload"], required=True,
                        help="Mode to run")
    parser.add_argument("--csv", help="CSV file path for upload mode")
    parser.add_argument("--db", default="outreach.db", help="Database file path")
    
    args = parser.parse_args()
    
    store = LeadStore(args.db)
    
    try:
        if args.mode == "upload":
            if not args.csv:
                LOGGER.error("--csv required for upload mode")
                sys.exit(1)
            count = load_csv(args.csv, store)
            print(f"Added {count} new leads")
            
        elif args.mode == "draft":
            count = run_draft_phase(store)
            print(f"Drafted {count} emails")
            
        elif args.mode == "send":
            count = run_send_phase(store)
            print(f"Sent {count} emails")
            
        elif args.mode == "daily":
            results = run_daily_cycle(store)
            print(f"Daily cycle complete: {results}")
            
        elif args.mode == "report":
            run_weekly_report(store)
            print("Weekly report generated")
            
    finally:
        store.close()


if __name__ == "__main__":
    main()
