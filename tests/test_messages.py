import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.models import GymMember, KeyHolder
from src.messages import current_key_holder_text


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


if __name__ == "__main__":
    unittest.main()
