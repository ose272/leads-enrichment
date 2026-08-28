"""Weekly report generator for the Outreach Agent."""

from __future__ import annotations

import csv
import logging
import os
from datetime import datetime, timezone
from typing import Any

from src.tracker import LeadStore
from src.mailer import send_email

LOGGER = logging.getLogger("reporter")


def generate_weekly_report(store: LeadStore, days: int = 7) -> dict[str, Any]:
    """Generate a weekly activity report.
    
    Args:
        store: LeadStore instance
        days: Number of days to look back (default 7)
        
    Returns:
        Dictionary with report statistics
    """
    stats = store.get_weekly_activity(days)
    
    # Add timestamp
    stats["report_generated"] = datetime.now(timezone.utc).isoformat()
    stats["period_days"] = days
    
    return stats


def save_report_csv(stats: dict[str, Any], filepath: str = "weekly_report.csv") -> None:
    """Save report as CSV."""
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Metric", "Value"])
        for key, value in stats.items():
            writer.writerow([key, value])
    
    LOGGER.info("Saved weekly report CSV to %s", filepath)


def save_report_html(stats: dict[str, Any], filepath: str = "weekly_report.html") -> None:
    """Save report as HTML."""
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Weekly Outreach Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 20px auto; padding: 20px; }}
        h1 {{ color: #2c3e50; }}
        .metric {{ display: flex; justify-content: space-between; padding: 10px; border-bottom: 1px solid #eee; }}
        .metric:nth-child(odd) {{ background: #f9f9f9; }}
        .label {{ font-weight: bold; color: #34495e; }}
        .value {{ color: #2c3e50; }}
        .section {{ margin-top: 30px; }}
        .positive {{ color: #27ae60; }}
        .negative {{ color: #e74c3c; }}
        .neutral {{ color: #f39c12; }}
    </style>
</head>
<body>
    <h1>Weekly Outreach Report</h1>
    <p>Generated: {stats.get('report_generated', 'N/A')}</p>
    <p>Period: Last {stats.get('period_days', 7)} days</p>
    
    <div class="section">
        <h2>Lead Pipeline</h2>
        <div class="metric"><span class="label">Total Leads</span><span class="value">{stats.get('total_leads', 0)}</span></div>
        <div class="metric"><span class="label">New Leads (this period)</span><span class="value">{stats.get('new_leads', 0)}</span></div>
        <div class="metric"><span class="label">Scraped</span><span class="value">{stats.get('scraped', 0)}</span></div>
        <div class="metric"><span class="label">Drafted</span><span class="value">{stats.get('drafted', 0)}</span></div>
        <div class="metric"><span class="label">Sent</span><span class="value">{stats.get('sent', 0)}</span></div>
        <div class="metric"><span class="label">Replied</span><span class="value">{stats.get('replied', 0)}</span></div>
        <div class="metric"><span class="label">Follow-ups Sent</span><span class="value">{stats.get('follow_ups_sent', 0)}</span></div>
        <div class="metric"><span class="label">Positive Handoffs</span><span class="value positive">{stats.get('positive_handoffs', 0)}</span></div>
    </div>
    
    <div class="section">
        <h2>Reply Sentiment Breakdown</h2>
        <div class="metric"><span class="label">Positive</span><span class="value positive">{stats.get('replies_positive', 0)}</span></div>
        <div class="metric"><span class="label">Neutral</span><span class="value neutral">{stats.get('replies_neutral', 0)}</span></div>
        <div class="metric"><span class="label">Negative</span><span class="value negative">{stats.get('replies_negative', 0)}</span></div>
    </div>
</body>
</html>"""
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)
    
    LOGGER.info("Saved weekly report HTML to %s", filepath)


def email_report(stats: dict[str, Any], recipient: str = None) -> bool:
    """Email the weekly report to a recipient."""
    recipient = recipient or os.getenv("SMTP_USER")
    
    if not recipient:
        LOGGER.warning("No recipient configured for weekly report")
        return False
    
    lines = [
        "Weekly Outreach Report",
        "=" * 30,
        f"Period: Last {stats.get('period_days', 7)} days",
        f"Generated: {stats.get('report_generated', 'N/A')}",
        "",
        "LEAD PIPELINE:",
        f"  Total Leads: {stats.get('total_leads', 0)}",
        f"  New Leads: {stats.get('new_leads', 0)}",
        f"  Scraped: {stats.get('scraped', 0)}",
        f"  Drafted: {stats.get('drafted', 0)}",
        f"  Sent: {stats.get('sent', 0)}",
        f"  Replied: {stats.get('replied', 0)}",
        f"  Follow-ups Sent: {stats.get('follow_ups_sent', 0)}",
        f"  Positive Handoffs: {stats.get('positive_handoffs', 0)}",
        "",
        "REPLY SENTIMENT:",
        f"  Positive: {stats.get('replies_positive', 0)}",
        f"  Neutral: {stats.get('replies_neutral', 0)}",
        f"  Negative: {stats.get('replies_negative', 0)}",
    ]
    
    body = "\n".join(lines)
    
    return send_email(
        recipient,
        f"Weekly Outreach Report - {datetime.now().strftime('%Y-%m-%d')}",
        body
    )


def run_weekly_report(store: LeadStore, days: int = 7, email_recipient: str = None) -> dict[str, Any]:
    """Run the complete weekly report generation workflow.
    
    Args:
        store: LeadStore instance
        days: Lookback period in days
        email_recipient: Optional email to send report to
        
    Returns:
        Report statistics dictionary
    """
    LOGGER.info("Generating weekly report...")
    
    stats = generate_weekly_report(store, days)
    
    save_report_csv(stats)
    save_report_html(stats)
    
    if email_recipient:
        email_report(stats, email_recipient)
    
    LOGGER.info("Weekly report complete")
    return stats

