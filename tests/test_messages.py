import sys
import unittest
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.models import GymMember, KeyHistoryRecord, KeyHolder, KeyStatus
from src.messages import current_key_holder_text, key_history_record_text, key_status_text


class MessageTests(unittest.TestCase):
    def test_current_key_holder_text_includes_contact_details_when_present(self):
        holder = KeyHolder(
            key_id=1,
            member=GymMember(
                id=10,
                telegram_user_id=123,
                name="Dima",
                surname="Ivanov",
                room_number=1234,
                telegram_name="@dima",
                phone_number="+49123456789",
                is_admin=False,
            ),
        )

        text = current_key_holder_text(holder)

        self.assertIn("Key 1", text)
        self.assertIn("Dima Ivanov", text)
        self.assertIn("room 1234", text)
        self.assertIn("Telegram: @dima", text)
        self.assertIn("Phone: +49123456789", text)

    def test_current_key_holder_text_skips_missing_contact_details(self):
        holder = KeyHolder(
            key_id=1,
            member=GymMember(
                id=10,
                telegram_user_id=123,
                name="Dima",
                surname="Ivanov",
                room_number=1234,
                telegram_name=None,
                phone_number=None,
                is_admin=False,
            ),
        )

        text = current_key_holder_text(holder)

        self.assertNotIn("Telegram:", text)
        self.assertNotIn("Phone:", text)

    def test_key_history_record_text_describes_transfer(self):
        record = KeyHistoryRecord(
            event_id=5,
            key_id=2,
            member=GymMember(10, 123, "Ada", "Lovelace", 1234, None, None, False),
            taken_at=datetime(2026, 6, 5, 12, 30),
        )

        self.assertEqual(
            "2026-06-05 12:30:00 UTC: key 2 received by Ada Lovelace, room 1234.",
            key_history_record_text(record),
        )

    def test_key_status_text_includes_full_status(self):
        status = KeyStatus(
            key_id=2,
            current_holder=GymMember(
                10, 123, "Ada", "Lovelace", 1234, "@ada", "+49123", False
            ),
            owner=GymMember(
                20, 456, "Key", "Mailbox", 4321, None, None, False
            ),
            is_active=False,
        )

        text = key_status_text(status)

        self.assertIn("Key ID: 2", text)
        self.assertIn("Active: no", text)
        self.assertIn("Current holder:", text)
        self.assertIn("Ada", text)
        self.assertIn("Owner:", text)
        self.assertIn("Mailbox", text)


if __name__ == "__main__":
    unittest.main()
