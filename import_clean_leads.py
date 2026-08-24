"""Clean invalid leads and ingest clean CSV leads into leads.db."""

from __future__ import annotations

import csv
import sqlite3
from ingest_service import LeadStore

DB_PATH = "leads.db"
CSV_PATH = "leads_for_ingest.csv"


def clean_and_import() -> None:
    store = LeadStore(DB_PATH)

    # Reset leads and processed messages for clean import
    with store.connection:
        store.connection.execute("DELETE FROM leads")
        store.connection.execute("DELETE FROM processed_messages WHERE message_id LIKE 'manual_clean_import%'")
        store.connection.execute("DELETE FROM conversation_log")

    # Read clean CSV
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))

    print(f"Read {len(reader)} clean leads from {CSV_PATH}")

    # Ingest using LeadStore
    inserted = store.insert_leads("manual_clean_import_v2", reader)
    print(f"Successfully inserted {inserted} leads into {DB_PATH}")

    cursor = store.connection.cursor()
    total_after = cursor.execute("SELECT count(*) FROM leads").fetchone()[0]
    with_company = cursor.execute("SELECT count(*) FROM leads WHERE company IS NOT NULL AND company != ''").fetchone()[0]
    with_website = cursor.execute("SELECT count(*) FROM leads WHERE website IS NOT NULL AND website != ''").fetchone()[0]
    with_phone = cursor.execute("SELECT count(*) FROM leads WHERE phone IS NOT NULL AND phone != ''").fetchone()[0]

    print(f"\nFinal Database Summary:")
    print(f"  Total Leads:  {total_after}")
    print(f"  With Company: {with_company}")
    print(f"  With Website: {with_website}")
    print(f"  With Phone:   {with_phone}")

    print("\nSample Ingested Leads:")
    for row in cursor.execute("SELECT id, company, phone, website, status FROM leads LIMIT 5").fetchall():
        print(f"  ID {row[0]}: {row[1]} | Phone: {row[2]} | Web: {row[3]} | Status: {row[4]}")

    store.close()


if __name__ == "__main__":
    clean_and_import()
