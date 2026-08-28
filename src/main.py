"""Main orchestration module for the Outreach Agent.

Modes:
- --mode daily: Run daily outreach cycle (scrape, draft, send, check replies, follow-ups)
- --mode report: Generate weekly report
- --mode scrape: Only scrape emails for new leads
- --mode upload: Upload CSV of websites
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Optional

from dotenv import load_dotenv

from src.tracker import LeadStore
from src.scraper import scrape_email, scrape_website_content
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
    """Load websites from CSV and add to leads table.
    
    Args:
        filepath: Path to CSV file with 'website' column
        store: LeadStore instance
        
    Returns:
        Number of new leads added
    """
    import pandas as pd
    
    if not os.path.exists(filepath):
        LOGGER.error("CSV file not found: %s", filepath)
        return 0
    
    df = pd.read_csv(filepath)
    
    if "website" not in df.columns:
        LOGGER.error("CSV must have a 'website' column")
        return 0
    
    # Clean and validate URLs
    websites = df["website"].dropna().astype(str).str.strip().str.lower()
    websites = websites[websites != ""]
    
    # Add https:// if missing
    def normalize_url(url: str) -> str:
        if not url.startswith(("http://", "https://")):
            return "https://" + url
        return url
    
    websites = websites.apply(normalize_url)
    websites = websites.drop_duplicates()
    
    added = 0
    for website in websites:
        try:
            lead_id = store.add_lead(website)
            if lead_id:
                added += 1
        except Exception as e:
            LOGGER.warning("Failed to add %s: %s", website, e)
    
    LOGGER.info("Loaded CSV: %d new leads added from %d unique websites", added, len(websites))
    return added


def run_scrape_phase(store: LeadStore) -> int:
    """Scrape emails for leads with status 'new'.
    
    Returns:
        Number of leads scraped
    """
    leads = store.get_leads_by_status("new")
    scraped = 0
    
    for lead in leads:
        LOGGER.info("Scraping email for %s", lead.website)
        
        try:
            # Try to get email and business context
            summary, emails = scrape_website_content(lead.website)
            
            if emails:
                email = emails[0]
                store.update_status(lead.id, "scraped", contact_email=email, notes=summary[:500])
                LOGGER.info("Found email for %s: %s", lead.website, email)
            else:
                # No email found, but we have context
                store.update_status(lead.id, "scraped", notes=summary[:500])
                LOGGER.info("No email found for %s, but got context", lead.website)
            
            scraped += 1
            
        except Exception as e:
            LOGGER.error("Error scraping %s: %s", lead.website, e)
            store.update_status(lead.id, "scraped", notes=f"Scrape error: {e}")
    
    return scraped


def run_draft_phase(store: LeadStore) -> int:
    """Draft emails for scraped leads with emails.
    
    Returns:
        Number of emails drafted
    """
    leads = store.get_leads_by_status("scraped")
    drafted = 0
    
    for lead in leads:
        if not lead.contact_email:
            LOGGER.info("Lead %d has no email, skipping draft", lead.id)
            continue
        
        LOGGER.info("Drafting email for %s", lead.website)
        
        try:
            # Use the scraped context for personalization
            draft = draft_email(lead.website, lead.notes or f"Website: {lead.website}")
            
            if draft:
                # Store draft in notes for now (could add separate fields)
                store.update_status(
                    lead.id, 
                    "drafted", 
                    notes=f"Subject: {draft.subject}\n\n{draft.body}"
                )
                drafted += 1
                LOGGER.info("Drafted email for %s: %s", lead.website, draft.subject[:50])
            else:
                LOGGER.warning("Failed to draft email for %s", lead.website)
                
        except Exception as e:
            LOGGER.error("Error drafting for %s: %s", lead.website, e)
    
    return drafted


def run_send_phase(store: LeadStore) -> int:
    """Send drafted emails.
    
    Returns:
        Number of emails sent
    """
    leads = store.get_leads_by_status("drafted")
    sent = 0
    
    for lead in leads:
        if not lead.contact_email:
            continue
        
        # Parse subject and body from notes
        notes = lead.notes or ""
        lines = notes.split("\n")
        subject = ""
        body = ""
        
        if lines and lines[0].startswith("Subject: "):
            subject = lines[0][9:]
            body = "\n".join(lines[2:])  # Skip empty line
        
        if not subject or not body:
            LOGGER.warning("Invalid draft for lead %d", lead.id)
            continue
        
        LOGGER.info("Sending email to %s", lead.contact_email)
        
        try:
            success = send_email(lead.contact_email, subject, body)
            
            if success:
                store.update_status(lead.id, "sent")
                sent += 1
                LOGGER.info("Sent email to %s", lead.contact_email)
            else:
                LOGGER.error("Failed to send email to %s", lead.contact_email)
                
        except Exception as e:
            LOGGER.error("Error sending to %s: %s", lead.contact_email, e)
    
    return sent


def run_followup_phase(store: LeadStore) -> int:
    """Send follow-ups to leads that haven't replied.
    
    Returns:
        Number of follow-ups sent
    """
    # Get leads in 'sent' status older than 3 days with no reply
    leads = store.get_leads_for_followup(days=3)
    sent = 0
    
    for lead in leads:
        if not lead.contact_email:
            continue
            
        LOGGER.info("Sending follow-up to %s (%s)", lead.contact_email, lead.website)
        
        try:
            followup = draft_followup(lead.website, lead.notes or "")
            
            if followup:
                success = send_email(lead.contact_email, followup.subject, followup.body)
                if success:
                    store.update_status(lead.id, "followup_sent")
                    sent += 1
                    LOGGER.info("Sent follow-up to %s", lead.contact_email)
                else:
                    LOGGER.error("Failed to send follow-up to %s", lead.contact_email)
            else:
                LOGGER.warning("Failed to draft follow-up for lead %d", lead.id)
                
        except Exception as e:
            LOGGER.error("Error sending follow-up to %s: %s", lead.contact_email, e)
    
    return sent


def run_daily_cycle(store: LeadStore) -> dict[str, int]:
    """Run the complete daily outreach cycle.
    
    Returns:
        Dictionary with counts for each phase
    """
    LOGGER.info("Starting daily outreach cycle")
    
    results = {}
    
    # Phase 1: Scrape new leads
    results["scraped"] = run_scrape_phase(store)
    
    # Phase 2: Draft emails
    results["drafted"] = run_draft_phase(store)
    
    # Phase 3: Send emails
    results["sent"] = run_send_phase(store)
    
    # Phase 4: Check replies
    results["replies_processed"] = check_replies(store)
    
    # Phase 5: Send follow-ups
    results["followups_sent"] = run_followup_phase(store)
    
    LOGGER.info("Daily cycle complete: %s", results)
    return results


def main():
    """Main entry point with command-line argument parsing."""
    parser = argparse.ArgumentParser(description="Outreach Agent - Automated cold outreach")
    parser.add_argument("--mode", choices=["daily", "report", "scrape", "upload"], required=True,
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
            
        elif args.mode == "scrape":
            count = run_scrape_phase(store)
            print(f"Scraped {count} leads")
            
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
