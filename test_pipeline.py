import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ingest_service import LeadStore
from outreach import contains_opt_out
from pipeline import classify_inbound, due_followup_status


class FakeLlm:
    def classify_reply_intent(self, message):
        return "ready-to-talk"


class PipelineTests(unittest.TestCase):
    def test_opt_out_is_detected_before_any_other_reply_logic(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LeadStore(str(Path(directory) / "leads.db"))
            with store.connection:
                store.connection.execute(
                    "INSERT INTO leads (email, status, source_message_id, created_at, raw_data) VALUES (?, 'emailed', ?, ?, '{}')",
                    ("lead@example.com", "message-1", datetime.now(timezone.utc).isoformat()),
                )
            lead_id = store.connection.execute("SELECT id FROM leads").fetchone()[0]
            self.assertTrue(contains_opt_out("Please unsubscribe me"))
            self.assertEqual(classify_inbound(store, lead_id, "Please unsubscribe me", FakeLlm()), "unsubscribed")
            self.assertEqual(store.connection.execute("SELECT status FROM leads WHERE id = ?", (lead_id,)).fetchone()[0], "unsubscribed")
            store.close()

    def test_follow_up_schedule_transitions(self):
        now = datetime.now(timezone.utc)
        old = (now - timedelta(days=2, minutes=1)).isoformat()
        self.assertEqual(due_followup_status(old, 0, now), "followup_1")
        self.assertEqual(due_followup_status(old, 1, now), "followup_2")
        archived_time = (now - timedelta(hours=24, minutes=1)).isoformat()
        self.assertEqual(due_followup_status(archived_time, 2, now), "archived_no_response")

    def test_classify_inbound_handles_all_intents(self):
        """Test that classify_inbound correctly handles all intent types."""
        with tempfile.TemporaryDirectory() as directory:
            store = LeadStore(str(Path(directory) / "leads.db"))
            with store.connection:
                store.connection.execute(
                    "INSERT INTO leads (email, status, source_message_id, created_at, raw_data) VALUES (?, 'emailed', ?, ?, '{}')",
                    ("lead@example.com", "message-1", datetime.now(timezone.utc).isoformat()),
                )
            lead_id = store.connection.execute("SELECT id FROM leads").fetchone()[0]

            class IntentLlm:
                def __init__(self, intent):
                    self.intent = intent
                def classify_reply_intent(self, message):
                    return self.intent

            for intent, expected_status in [
                ("curious", "curious"),
                ("objecting", "objecting"),
                ("neutral", "neutral"),
                ("ready-to-talk", "handed_off"),
            ]:
                with store.connection:
                    store.connection.execute("UPDATE leads SET status = 'emailed' WHERE id = ?", (lead_id,))
                result = classify_inbound(store, lead_id, "Some reply", IntentLlm(intent))
                self.assertEqual(result, expected_status)
                db_status = store.connection.execute("SELECT status FROM leads WHERE id = ?", (lead_id,)).fetchone()[0]
                self.assertEqual(db_status, expected_status)
            store.close()


if __name__ == "__main__":
    unittest.main()
