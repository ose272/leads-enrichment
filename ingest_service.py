"""Poll an IMAP Drafts folder and ingest matching lead CSV attachments into SQLite."""

from __future__ import annotations

import csv
import email
import hashlib
import imaplib
import io
import json
import logging
import os
import sqlite3
import ssl
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email import policy
from email.message import Message
from typing import Any, Iterable


LOGGER = logging.getLogger("lead_ingestion")


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
    imap_host: str
    imap_port: int
    imap_user: str
    imap_password: str
    drafts_folder: str = "Drafts"
    processed_folder: str = "Processed"
    poll_interval_seconds: int = 300
    database_path: str = "leads.db"
    filename_marker: str = "leads_"
    subject_tag: str = "[NEW LEADS]"

    @classmethod
    def from_env(cls) -> "Settings":
        required = ("IMAP_HOST", "IMAP_USER", "IMAP_PASSWORD")
        missing = [name for name in required if not os.getenv(name)]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        return cls(
            imap_host=os.environ["IMAP_HOST"],
            imap_port=int(os.getenv("IMAP_PORT", "993")),
            imap_user=os.environ["IMAP_USER"],
            imap_password=os.environ["IMAP_PASSWORD"],
            drafts_folder=os.getenv("IMAP_DRAFTS_FOLDER", "Drafts"),
            processed_folder=os.getenv("IMAP_PROCESSED_FOLDER", "Processed"),
            poll_interval_seconds=int(os.getenv("POLL_INTERVAL_SECONDS", "300")),
            database_path=os.getenv("DATABASE_PATH", "leads.db"),
            filename_marker=os.getenv("CSV_FILENAME_MARKER", "leads_"),
            subject_tag=os.getenv("SUBJECT_TAG", "[NEW LEADS]"),
        )


class LeadStore:
    """SQLite persistence with a message-level idempotency record."""

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
                processed_at TEXT NOT NULL,
                lead_count INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS conversation_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER NOT NULL,
                direction TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (lead_id) REFERENCES leads(id)
            );
            """
        )
        existing_columns = {
            row[1] for row in self.connection.execute("PRAGMA table_info(leads)").fetchall()
        }
        migrations = {
            "scraped_summary": "TEXT",
            "personalization_angle": "TEXT",
            "last_contacted_at": "TEXT",
            "followup_count": "INTEGER NOT NULL DEFAULT 0",
            "thread_id": "TEXT",
            "campaign_batch": "TEXT",
        }
        for column, definition in migrations.items():
            if column not in existing_columns:
                self.connection.execute(f"ALTER TABLE leads ADD COLUMN {column} {definition}")
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def is_processed(self, message_id: str) -> bool:
        row = self.connection.execute(
            "SELECT 1 FROM processed_messages WHERE message_id = ?", (message_id,)
        ).fetchone()
        return row is not None

    def insert_leads(self, message_id: str, rows: list[dict[str, str]]) -> int:
        if self.is_processed(message_id):
            return 0
        now = datetime.now(timezone.utc).isoformat()
        with self.connection:
            self.connection.executemany(
                """
                INSERT INTO leads
                    (email, first_name, last_name, company, phone, website,
                     status, source_message_id, created_at, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, 'new', ?, ?, ?)
                """,
                [
                    (
                        value_for(row, "email"),
                        value_for(row, "first_name", "firstname", "first"),
                        value_for(row, "last_name", "lastname", "last"),
                        value_for(row, "company", "company_name", "organization"),
                        value_for(row, "phone", "phone_number", "mobile"),
                        value_for(row, "website", "url"),
                        message_id,
                        now,
                        json.dumps(row, ensure_ascii=True, sort_keys=True),
                    )
                    for row in rows
                ],
            )
            self.connection.execute(
                "INSERT INTO processed_messages VALUES (?, ?, ?)",
                (message_id, now, len(rows)),
            )
        return len(rows)


def value_for(row: dict[str, str], *names: str) -> str:
    normalized = {key.strip().lower().replace(" ", "_"): value.strip() for key, value in row.items()}
    for name in names:
        if normalized.get(name):
            return normalized[name]
    return ""


def message_identifier(message: Message, uid: bytes | str) -> str:
    message_id = message.get("Message-ID")
    if message_id:
        return message_id.strip()
    return f"imap-uid:{uid.decode() if isinstance(uid, bytes) else uid}"


def matching_attachments(
    message: Message, filename_marker: str, subject_tag: str
) -> list[tuple[str, bytes]]:
    subject = message.get("Subject", "")
    subject_matches = subject_tag.lower() in subject.lower()
    matches: list[tuple[str, bytes]] = []
    for part in message.walk():
        filename = part.get_filename()
        if not filename or part.get_content_disposition() != "attachment":
            continue
        if not filename.lower().endswith(".csv"):
            continue
        if filename_marker.lower() not in filename.lower() and not subject_matches:
            continue
        payload = part.get_payload(decode=True)
        if payload is not None:
            matches.append((filename, payload))
    return matches


def parse_csv(payload: bytes) -> list[dict[str, str]]:
    text = payload.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV attachment has no header row")
    rows = [{str(key): (value or "") for key, value in row.items() if key is not None} for row in reader]
    return rows


class ImapLeadIngestor:
    def __init__(self, settings: Settings, store: LeadStore) -> None:
        self.settings = settings
        self.store = store

    def connect(self) -> imaplib.IMAP4_SSL:
        client = imaplib.IMAP4_SSL(self.settings.imap_host, self.settings.imap_port, ssl_context=ssl.create_default_context())
        client.login(self.settings.imap_user, self.settings.imap_password)
        return client

    def run_once(self, client: Any) -> int:
        status, _ = client.select(self.settings.drafts_folder)
        if status != "OK":
            raise RuntimeError(f"Could not select IMAP folder: {self.settings.drafts_folder}")
        status, data = client.uid("SEARCH", None, "ALL")
        if status != "OK":
            raise RuntimeError("Could not search IMAP Drafts")

        total = 0
        for uid in (data[0] or b"").split():
            status, fetched = client.uid("FETCH", uid, "(RFC822)")
            if status != "OK" or not fetched or not fetched[0]:
                LOGGER.warning("Could not fetch draft UID %s", uid)
                continue
            raw_message = fetched[0][1]
            message = email.message_from_bytes(raw_message, policy=policy.default)
            identifier = message_identifier(message, uid)
            if self.store.is_processed(identifier):
                continue
            attachments = matching_attachments(message, self.settings.filename_marker, self.settings.subject_tag)
            if not attachments:
                continue
            rows = [row for _, payload in attachments for row in parse_csv(payload)]
            if not rows:
                LOGGER.info("Skipping empty lead CSV in draft %s", identifier)
                continue
            inserted = self.store.insert_leads(identifier, rows)
            self._mark_processed(client, uid)
            total += inserted
            LOGGER.info("Ingested %d leads from draft %s", inserted, identifier)
        return total

    def _mark_processed(self, client: Any, uid: bytes) -> None:
        status, _ = client.uid("COPY", uid, self.settings.processed_folder)
        if status == "OK":
            client.uid("STORE", uid, "+FLAGS", "(\\Deleted)")
            client.expunge()
            return
        # A visible marker still prevents accidental reprocessing if the folder is unavailable.
        client.uid("STORE", uid, "+FLAGS", "(\\Seen)")
        LOGGER.warning("Could not move UID %s to %s; marked it seen", uid, self.settings.processed_folder)


def run_forever(settings: Settings) -> None:
    store = LeadStore(settings.database_path)
    try:
        while True:
            client = None
            try:
                client = ImapLeadIngestor(settings, store).connect()
                ImapLeadIngestor(settings, store).run_once(client)
            except Exception:
                LOGGER.exception("Lead ingestion poll failed")
            finally:
                if client is not None:
                    try:
                        client.logout()
                    except Exception:
                        LOGGER.debug("IMAP logout failed", exc_info=True)
            time.sleep(settings.poll_interval_seconds)
    finally:
        store.close()


def main() -> None:
    load_env_file()
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
    run_forever(Settings.from_env())


if __name__ == "__main__":
    main()
