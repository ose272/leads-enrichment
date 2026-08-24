import email
import sqlite3
import tempfile
import unittest
from email.message import EmailMessage
from pathlib import Path

from ingest_service import ImapLeadIngestor, LeadStore, Settings


class FakeImap:
    def __init__(self, raw_message: bytes):
        self.raw_message = raw_message
        self.moved = False
        self.deleted = False

    def select(self, folder):
        self.folder = folder
        return "OK", [b"1"]

    def uid(self, command, uid=None, *args):
        if command == "SEARCH":
            return "OK", [b"1"]
        if command == "FETCH":
            return "OK", [(b"header", self.raw_message)]
        if command == "COPY":
            self.moved = True
            return "OK", [b""]
        if command == "STORE":
            self.deleted = "Deleted" in str(args)
            return "OK", [b""]
        raise AssertionError(command)

    def expunge(self):
        return "OK", [b""]


class IngestionTests(unittest.TestCase):
    def test_matching_csv_is_inserted_once_and_moved(self):
        message = EmailMessage()
        message["Message-ID"] = "<draft-1@example.test>"
        message["Subject"] = "[NEW LEADS] weekly import"
        message.set_content("attached")
        message.add_attachment(
            b"email,first_name,company\nada@example.com,Ada,Example Co\n",
            maintype="text",
            subtype="csv",
            filename="export.csv",
        )

        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "leads.db"
            store = LeadStore(str(database))
            settings = Settings("host", 993, "user", "password", poll_interval_seconds=1)
            ingestor = ImapLeadIngestor(settings, store)
            client = FakeImap(message.as_bytes())

            self.assertEqual(ingestor.run_once(client), 1)
            self.assertTrue(client.moved)
            self.assertTrue(client.deleted)
            self.assertEqual(ingestor.run_once(client), 0)
            row = store.connection.execute("SELECT email, first_name, status FROM leads").fetchone()
            self.assertEqual(tuple(row), ("ada@example.com", "Ada", "new"))
            self.assertEqual(store.connection.execute("SELECT COUNT(*) FROM leads").fetchone()[0], 1)
            store.close()

    def test_unrelated_csv_is_ignored(self):
        message = EmailMessage()
        message["Message-ID"] = "<draft-2@example.test>"
        message["Subject"] = "notes"
        message.set_content("attached")
        message.add_attachment(b"email\na@example.com\n", maintype="text", subtype="csv", filename="notes.csv")

        with tempfile.TemporaryDirectory() as directory:
            store = LeadStore(str(Path(directory) / "leads.db"))
            settings = Settings("host", 993, "user", "password")
            self.assertEqual(ImapLeadIngestor(settings, store).run_once(FakeImap(message.as_bytes())), 0)
            self.assertEqual(store.connection.execute("SELECT COUNT(*) FROM leads").fetchone()[0], 0)
            store.close()


if __name__ == "__main__":
    unittest.main()
