"""Database storage layer for SE Global Outreach Agent.

Provides LeadStore for SQLite persistence and Settings for configuration.
No IMAP dependencies - used by dashboard upload and main service.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

LOGGER = logging.getLogger("storage")


def load_env_file(path: str = ".env") -> None:
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


@dataclass(frozen=True)
class Settings:
    database_path: str = "leads.db"
    imap_host: str = ""
    imap_port: int = 993
    imap_user: str = ""
    imap_password: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_path=os.getenv("DATABASE_PATH", "leads.db"),
            imap_host=os.getenv("IMAP_HOST", ""),
            imap_port=int(os.getenv("IMAP_PORT", "993")),
            imap_user=os.getenv("IMAP_USER", ""),
            imap_password=os.getenv("IMAP_PASSWORD", ""),
        )


class LeadStore:
    """SQLite persistence with idempotency via source_message_id."""

    def __init__(self, database_path: str) -> None:
        self.connection = sqlite3.connect(database_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT,
                first_name TEXT,
                last_name TEXT,
                company TEXT,
                phone TEXT,
                website TEXT,
                scraped_summary TEXT,
                personalization_angle TEXT,
                last_contacted_at TEXT,
                followup_count INTEGER NOT NULL DEFAULT 0,
                thread_id TEXT,
                campaign_batch TEXT,
                status TEXT NOT NULL DEFAULT 'new',
                source_message_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                raw_data TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS processed_messages (
                message_id TEXT PRIMARY KEY,
                processed_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS conversation_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER NOT NULL,
                direction TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (lead_id) REFERENCES leads (id)
            );

            CREATE INDEX IF NOT EXISTS idx_leads_status ON leads (status);
            CREATE INDEX IF NOT EXISTS idx_leads_email ON leads (email);
            CREATE INDEX IF NOT EXISTS idx_conversation_lead ON conversation_log (lead_id);
            """
        )

    def close(self) -> None:
        self.connection.close()

    def is_processed(self, message_id: str) -> bool:
        row = self.connection.execute(
            "SELECT 1 FROM processed_messages WHERE message_id = ?", (message_id,)
        ).fetchone()
        return row is not None

    def mark_processed(self, message_id: str) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT OR IGNORE INTO processed_messages (message_id, processed_at) VALUES (?, ?)",
                (message_id, datetime.now(timezone.utc).isoformat()),
            )

    def insert_leads(self, source_message_id: str, rows: Iterable[dict[str, Any]]) -> int:
        inserted = 0
        now = datetime.now(timezone.utc).isoformat()
        for row in rows:
            website = row.get("website") or row.get("Website") or row.get("url") or row.get("URL")
            if not website:
                LOGGER.warning("Skipping row with no website: %s", row)
                continue

            website = website.strip()
            if not website.startswith(("http://", "https://")):
                website = "https://" + website

            lead_idempotency_key = hashlib.sha256(website.encode()).hexdigest()[:16]
            full_source_id = f"{source_message_id}:{lead_idempotency_key}"

            if self.is_processed(full_source_id):
                continue

            raw_data = json.dumps(row, ensure_ascii=False)
            with self.connection:
                self.connection.execute(
                    """
                    INSERT INTO leads (
                        email, first_name, last_name, company, phone, website,
                        scraped_summary, personalization_angle, last_contacted_at,
                        followup_count, thread_id, campaign_batch, status,
                        source_message_id, created_at, raw_data
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("email") or row.get("Email") or "",
                        row.get("first_name") or row.get("First Name") or "",
                        row.get("last_name") or row.get("Last Name") or "",
                        row.get("company") or row.get("Company") or "",
                        row.get("phone") or row.get("Phone") or "",
                        website,
                        "",
                        "",
                        None,
                        0,
                        None,
                        source_message_id,
                        "new",
                        full_source_id,
                        now,
                        raw_data,
                    ),
                )
                self.mark_processed(full_source_id)
                inserted += 1
        return inserted

    def get_leads_for_enrichment(self) -> list[sqlite3.Row]:
        return self.connection.execute(
            "SELECT id, website FROM leads WHERE status = 'new' AND (scraped_summary IS NULL OR scraped_summary = '')"
        ).fetchall()

    def update_enriched_lead(self, lead_id: int, email: str, summary: str, status: str) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE leads SET email = ?, scraped_summary = ?, status = ? WHERE id = ?",
                (email, summary, status, lead_id),
            )

    def get_leads_for_outreach(self) -> list[sqlite3.Row]:
        return self.connection.execute(
            "SELECT id, email, first_name, company, scraped_summary, thread_id FROM leads "
            "WHERE status = 'new' AND email IS NOT NULL AND email != ''"
        ).fetchall()

    def mark_emailed(self, lead_id: int, thread_id: str) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE leads SET status = 'emailed', last_contacted_at = ?, thread_id = ?, followup_count = 0 WHERE id = ?",
                (datetime.now(timezone.utc).isoformat(), thread_id, lead_id),
            )
            self.connection.execute(
                "INSERT INTO conversation_log (lead_id, direction, message, timestamp) VALUES (?, 'outbound', ?, ?)",
                (lead_id, f"Initial outreach sent (thread: {thread_id})", datetime.now(timezone.utc).isoformat()),
            )

    def get_due_followups(self) -> list[sqlite3.Row]:
        return self.connection.execute(
            "SELECT id, email, first_name, company, scraped_summary, thread_id, followup_count, last_contacted_at "
            "FROM leads WHERE status = 'emailed' AND thread_id IS NOT NULL"
        ).fetchall()

    def mark_followup_sent(self, lead_id: int, followup_count: int, thread_id: str) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE leads SET followup_count = ?, last_contacted_at = ? WHERE id = ?",
                (followup_count, datetime.now(timezone.utc).isoformat(), lead_id),
            )
            self.connection.execute(
                "INSERT INTO conversation_log (lead_id, direction, message, timestamp) VALUES (?, 'outbound', ?, ?)",
                (lead_id, f"Follow-up #{followup_count} sent", datetime.now(timezone.utc).isoformat()),
            )

    def log_inbound_reply(self, lead_id: int, message: str, status: str) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT INTO conversation_log (lead_id, direction, message, timestamp) VALUES (?, 'inbound', ?, ?)",
                (lead_id, message, datetime.now(timezone.utc).isoformat()),
            )
            self.connection.execute("UPDATE leads SET status = ? WHERE id = ?", (status, lead_id))

    def get_weekly_stats(self, since: datetime) -> dict[str, Any]:
        week_ago = since.isoformat()
        stats = {}
        stats["total_leads"] = self.connection.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        stats["new_leads"] = self.connection.execute("SELECT COUNT(*) FROM leads WHERE status = 'new'").fetchone()[0]
        stats["emailed"] = self.connection.execute("SELECT COUNT(*) FROM leads WHERE status = 'emailed'").fetchone()[0]
        stats["replied"] = self.connection.execute("SELECT COUNT(*) FROM leads WHERE status IN ('replied', 'curious', 'objecting', 'handed_off')").fetchone()[0]
        stats["unsubscribed"] = self.connection.execute("SELECT COUNT(*) FROM leads WHERE status = 'unsubscribed'").fetchone()[0]
        stats["no_email_found"] = self.connection.execute("SELECT COUNT(*) FROM leads WHERE status = 'no_email_found'").fetchone()[0]
        stats["archived_no_response"] = self.connection.execute("SELECT COUNT(*) FROM leads WHERE status = 'archived_no_response'").fetchone()[0]

        stats["outbound_sent"] = self.connection.execute(
            "SELECT COUNT(*) FROM conversation_log WHERE direction = 'outbound' AND timestamp >= ?", (week_ago,)
        ).fetchone()[0]
        stats["inbound_received"] = self.connection.execute(
            "SELECT COUNT(*) FROM conversation_log WHERE direction = 'inbound' AND timestamp >= ?", (week_ago,)
        ).fetchone()[0]

        stats["top_companies"] = self.connection.execute(
            "SELECT company, COUNT(*) as replies FROM leads l JOIN conversation_log c ON l.id = c.lead_id "
            "WHERE c.direction = 'inbound' AND c.timestamp >= ? AND l.company IS NOT NULL "
            "GROUP BY company ORDER BY replies DESC LIMIT 5", (week_ago,)
        ).fetchall()
        return stats