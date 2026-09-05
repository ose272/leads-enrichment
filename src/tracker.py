"""Database storage layer for the Outreach Agent.

Provides LeadStore for SQLite persistence with the schema:
- id: integer primary key
- website: text (store URL)
- contact_email: text
- store_name: text (Shopify store name)
- owner_name: text (store owner name)
- status: text (new/drafted/sent/replied/follow_up_1/follow_up_2/closed/closed_handoff/no_email)
- first_contacted_date: text (ISO format)
- last_contacted_date: text (ISO format)
- follow_up_count: integer default 0
- reply_text: text
- reply_sentiment: text (positive/neutral/negative)
- notes: text
- last_email_subject: text
- last_email_body: text
- paraphrase_seed: integer (for tracking email variations)
- created_at: text (ISO format)
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

LOGGER = logging.getLogger("tracker")


@dataclass
class Lead:
    """Represents a lead in the database."""
    id: Optional[int]
    website: str
    contact_email: str
    store_name: str
    owner_name: str
    status: str
    first_contacted_date: Optional[str]
    last_contacted_date: Optional[str]
    follow_up_count: int
    reply_text: Optional[str]
    reply_sentiment: Optional[str]
    notes: Optional[str]
    last_email_subject: Optional[str] = None
    last_email_body: Optional[str] = None
    company_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    paraphrase_seed: int = 0


class LeadStore:
    """SQLite persistence for leads with follow-up tracking."""

    def __init__(self, database_path: str = "leads.db") -> None:
        self.database_path = database_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database schema."""
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    website TEXT NOT NULL,
                    contact_email TEXT,
                    store_name TEXT,
                    owner_name TEXT,
                    company_name TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    status TEXT NOT NULL DEFAULT 'new',
                    first_contacted_date TEXT,
                    last_contacted_date TEXT,
                    follow_up_count INTEGER NOT NULL DEFAULT 0,
                    reply_text TEXT,
                    reply_sentiment TEXT,
                    notes TEXT,
                    last_email_subject TEXT,
                    last_email_body TEXT,
                    paraphrase_seed INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_leads_status ON leads (status);
                CREATE INDEX IF NOT EXISTS idx_leads_email ON leads (contact_email);
                CREATE INDEX IF NOT EXISTS idx_leads_website ON leads (website);
            """)
            
            # Add new columns if they don't exist (for existing databases)
            for col in ['last_email_subject', 'last_email_body', 'company_name', 'first_name', 'last_name', 'updated_at', 'store_name', 'owner_name', 'paraphrase_seed']:
                try:
                    conn.execute(f"ALTER TABLE leads ADD COLUMN {col} TEXT")
                except sqlite3.OperationalError:
                    pass  # Column already exists
            
            # paraphrase_seed needs to be integer
            try:
                conn.execute("ALTER TABLE leads ADD COLUMN paraphrase_seed INTEGER NOT NULL DEFAULT 0")
            except sqlite3.OperationalError:
                pass

    def add_lead(
        self,
        website: str,
        contact_email: str = "",
        store_name: str = "",
        owner_name: str = "",
        company_name: str = "",
        first_name: str = "",
        last_name: str = "",
        paraphrase_seed: int = 0
    ) -> int:
        """Add a new lead or return existing lead ID. Returns the lead ID."""
        website = website.strip().lower()
        if not website.startswith(("http://", "https://")):
            website = "https://" + website

        with self._get_connection() as conn:
            # Check if already exists
            existing = conn.execute(
                "SELECT id FROM leads WHERE website = ?", (website,)
            ).fetchone()
            if existing:
                return existing["id"]

            # Insert new lead
            cursor = conn.execute(
                """INSERT INTO leads (website, contact_email, store_name, owner_name, company_name, first_name, last_name, status, paraphrase_seed, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'new', ?, ?)""",
                (website, contact_email or None, store_name or None, owner_name or None, company_name or None, first_name or None, last_name or None, paraphrase_seed, datetime.now(timezone.utc).isoformat())
            )
            return cursor.lastrowid

    def update_status(
        self,
        lead_id: int,
        status: str,
        contact_email: str = None,
        reply_text: str = None,
        reply_sentiment: str = None,
        notes: str = None,
        email_subject: str = None,
        email_body: str = None
    ) -> None:
        """Update lead status and optional fields."""
        with self._get_connection() as conn:
            updates = ["status = ?"]
            params = [status]

            now = datetime.now(timezone.utc).isoformat()

            if status in ("sent", "follow_up_1", "follow_up_2") and not self._get_first_contacted(lead_id):
                updates.append("first_contacted_date = ?")
                params.append(now)

            if status in ("sent", "follow_up_1", "follow_up_2", "replied"):
                updates.append("last_contacted_date = ?")
                params.append(now)

            if contact_email:
                updates.append("contact_email = ?")
                params.append(contact_email)

            if reply_text is not None:
                updates.append("reply_text = ?")
                params.append(reply_text)

            if reply_sentiment is not None:
                updates.append("reply_sentiment = ?")
                params.append(reply_sentiment)

            if notes is not None:
                updates.append("notes = ?")
                params.append(notes)

            if email_subject is not None:
                updates.append("last_email_subject = ?")
                params.append(email_subject)

            if email_body is not None:
                updates.append("last_email_body = ?")
                params.append(email_body)

            if status.startswith("follow_up_"):
                updates.append("follow_up_count = follow_up_count + 1")

            # Always update the updated_at timestamp
            updates.append("updated_at = ?")
            params.append(now)

            params.append(lead_id)

            conn.execute(
                f"UPDATE leads SET {', '.join(updates)} WHERE id = ?",
                params
            )
            conn.commit()

    def get_lead(self, lead_id: int) -> Optional[Lead]:
        """Get a lead by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
            return self._row_to_lead(row) if row else None

    def get_lead_by_website(self, website: str) -> Optional[Lead]:
        """Get a lead by website URL.
        
        Args:
            website: Website URL to search for
            
        Returns:
            Lead object if found, None otherwise
        """
        website = website.strip().lower()
        if not website.startswith(("http://", "https://")):
            website = "https://" + website
            
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM leads WHERE website = ?", (website,)).fetchone()
            return self._row_to_lead(row) if row else None

    def get_lead_by_email(self, email: str) -> Optional[Lead]:
        """Get a lead by email address.
        
        Args:
            email: Email address to search for
            
        Returns:
            Lead object if found, None otherwise
        """
        email = email.strip().lower()
        
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM leads WHERE contact_email = ?", (email,)).fetchone()
            return self._row_to_lead(row) if row else None

    def get_leads_by_status(self, status: str) -> list[Lead]:
        """Get all leads with a specific status."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM leads WHERE status = ? ORDER BY created_at", (status,)
            ).fetchall()
            return [self._row_to_lead(row) for row in rows]

    def get_leads_by_email(self, email: str) -> list[Lead]:
        """Get all leads with a specific contact email."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM leads WHERE contact_email = ? ORDER BY created_at", (email.lower(),)
            ).fetchall()
            return [self._row_to_lead(row) for row in rows]

    def get_weekly_activity(self, days: int = 7) -> dict[str, Any]:
        """Get activity stats for the past N days."""
        with self._get_connection() as conn:
            since = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            since = since.replace(day=since.day - days).isoformat()

            stats = {}
            stats["new_leads"] = conn.execute(
                "SELECT COUNT(*) FROM leads WHERE created_at >= ?", (since,)
            ).fetchone()[0]
            stats["scraped"] = conn.execute(
                "SELECT COUNT(*) FROM leads WHERE status = 'scraped' AND created_at >= ?", (since,)
            ).fetchone()[0]
            stats["drafted"] = conn.execute(
                "SELECT COUNT(*) FROM leads WHERE status = 'drafted' AND created_at >= ?", (since,)
            ).fetchone()[0]
            stats["sent"] = conn.execute(
                "SELECT COUNT(*) FROM leads WHERE status = 'sent' AND created_at >= ?", (since,)
            ).fetchone()[0]
            stats["replied"] = conn.execute(
                "SELECT COUNT(*) FROM leads WHERE status = 'replied' AND created_at >= ?", (since,)
            ).fetchone()[0]
            stats["follow_ups_sent"] = conn.execute(
                "SELECT COUNT(*) FROM leads WHERE status LIKE 'follow_up_%' AND last_contacted_date >= ?", (since,)
            ).fetchone()[0]
            stats["positive_handoffs"] = conn.execute(
                "SELECT COUNT(*) FROM leads WHERE reply_sentiment = 'positive' AND reply_text IS NOT NULL AND last_contacted_date >= ?", (since,)
            ).fetchone()[0]

            # Sentiment breakdown
            stats["replies_positive"] = conn.execute(
                "SELECT COUNT(*) FROM leads WHERE reply_sentiment = 'positive' AND last_contacted_date >= ?", (since,)
            ).fetchone()[0]
            stats["replies_neutral"] = conn.execute(
                "SELECT COUNT(*) FROM leads WHERE reply_sentiment = 'neutral' AND last_contacted_date >= ?", (since,)
            ).fetchone()[0]
            stats["replies_negative"] = conn.execute(
                "SELECT COUNT(*) FROM leads WHERE reply_sentiment = 'negative' AND last_contacted_date >= ?", (since,)
            ).fetchone()[0]

            return stats

    def get_leads_for_followup(self, days: int = 2) -> list[Lead]:
        """Get leads eligible for follow-up.
        
        Args:
            days: Number of days since last contact
            
        Returns:
            List of leads eligible for follow-up
        """
        with self._get_connection() as conn:
            # Calculate cutoff date
            from datetime import datetime, timezone, timedelta
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            cutoff_str = cutoff.isoformat()
            
            # Get leads in 'sent' or 'follow_up_1' status older than specified days with no reply
            # and follow_up_count < 2 (max 2 follow-ups)
            rows = conn.execute(
                """
                SELECT * FROM leads 
                WHERE status IN ('sent', 'follow_up_1') 
                AND last_contacted_date IS NOT NULL
                AND last_contacted_date <= ?
                AND follow_up_count < 2
                AND reply_text IS NULL
                ORDER BY last_contacted_date ASC
                """,
                (cutoff_str,)
            ).fetchall()
            
            return [self._row_to_lead(row) for row in rows]

    def _row_to_lead(self, row: sqlite3.Row) -> Lead:
        return Lead(
            id=row["id"],
            website=row["website"],
            contact_email=row["contact_email"] or "",
            store_name=row["store_name"] or "",
            owner_name=row["owner_name"] or "",
            status=row["status"],
            first_contacted_date=row["first_contacted_date"],
            last_contacted_date=row["last_contacted_date"],
            follow_up_count=row["follow_up_count"],
            reply_text=row["reply_text"],
            reply_sentiment=row["reply_sentiment"],
            notes=row["notes"],
            last_email_subject=row["last_email_subject"],
            last_email_body=row["last_email_body"],
            company_name=row["company_name"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            paraphrase_seed=row["paraphrase_seed"] if "paraphrase_seed" in row.keys() else 0,
        )

    def _get_first_contacted(self, lead_id: int) -> Optional[str]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT first_contacted_date FROM leads WHERE id = ?", (lead_id,)
            ).fetchone()
            return row["first_contacted_date"] if row else None

    @contextmanager
    def _get_connection(self):
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def close(self) -> None:
        """Close any open connections (placeholder for future use)."""
        pass
