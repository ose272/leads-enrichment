"""Database storage layer for the Outreach Agent.

Provides LeadStore for SQLite persistence with the schema:
- id: integer primary key
- website: text
- contact_email: text
- status: text (new/scraped/drafted/sent/replied/follow_up_1/follow_up_2/closed)
- first_contacted_date: text (ISO format)
- last_contacted_date: text (ISO format)
- follow_up_count: integer default 0
- reply_text: text
- reply_sentiment: text (positive/neutral/negative)
- notes: text
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
    status: str
    first_contacted_date: Optional[str]
    last_contacted_date: Optional[str]
    follow_up_count: int
    reply_text: Optional[str]
    reply_sentiment: Optional[str]
    notes: Optional[str]


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
                    status TEXT NOT NULL DEFAULT 'new',
                    first_contacted_date TEXT,
                    last_contacted_date TEXT,
                    follow_up_count INTEGER NOT NULL DEFAULT 0,
                    reply_text TEXT,
                    reply_sentiment TEXT,
                    notes TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_leads_status ON leads (status);
                CREATE INDEX IF NOT EXISTS idx_leads_email ON leads (contact_email);
                CREATE INDEX IF NOT EXISTS idx_leads_website ON leads (website);
            """)

    def add_lead(self, website: str, contact_email: str = "") -> int:
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
                """INSERT INTO leads (website, contact_email, status, created_at)
                   VALUES (?, ?, 'new', ?)""",
                (website, contact_email or None, datetime.now(timezone.utc).isoformat())
            )
            return cursor.lastrowid

    def update_status(
        self,
        lead_id: int,
        status: str,
        contact_email: str = None,
        reply_text: str = None,
        reply_sentiment: str = None,
        notes: str = None
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

            if status.startswith("follow_up_"):
                updates.append("follow_up_count = follow_up_count + 1")

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

    def get_leads_by_status(self, status: str) -> list[Lead]:
        """Get all leads with a specific status."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM leads WHERE status = ? ORDER BY created_at", (status,)
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

    def get_leads_for_followup(self, days: int = 3) -> list[Lead]:
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
            
            # Get leads in 'sent' status older than specified days with no reply
            # and follow_up_count < 2 (max 2 follow-ups)
            rows = conn.execute(
                """
                SELECT * FROM leads 
                WHERE status = 'sent' 
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
            status=row["status"],
            first_contacted_date=row["first_contacted_date"],
            last_contacted_date=row["last_contacted_date"],
            follow_up_count=row["follow_up_count"],
            reply_text=row["reply_text"],
            reply_sentiment=row["reply_sentiment"],
            notes=row["notes"],
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
