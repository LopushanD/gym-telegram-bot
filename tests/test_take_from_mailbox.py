import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.key_service import (
    TakeFromMailboxStatus,
    take_key_from_mailbox,
)


class TakeFromMailboxTests(unittest.TestCase):
    def test_take_key_from_mailbox_updates_holder_to_member(self):
        with (
            patch("src.key_service.get_current_key_holder_info", return_value=("Mailbox", "", 0)),
            patch("src.key_service.get_gym_member_id_by_telegram_user_id", return_value=42),
            patch("src.key_service.change_key_holder") as change_key_holder,
        ):
            result = take_key_from_mailbox("database.sqlite3", 123, key_id=1)

        self.assertEqual(TakeFromMailboxStatus.TAKEN, result.status)
        change_key_holder.assert_called_once_with("database.sqlite3", 1, 42)

    def test_take_key_from_mailbox_rejects_when_key_is_not_in_mailbox(self):
        with (
            patch("src.key_service.get_current_key_holder_info", return_value=None),
            patch("src.key_service.get_gym_member_id_by_telegram_user_id") as get_member_id,
            patch("src.key_service.change_key_holder") as change_key_holder,
        ):
            result = take_key_from_mailbox("database.sqlite3", 123, key_id=1)

        self.assertEqual(TakeFromMailboxStatus.KEY_NOT_IN_MAILBOX, result.status)
        get_member_id.assert_not_called()
        change_key_holder.assert_not_called()

    def test_take_key_from_mailbox_rejects_missing_telegram_user(self):
        with (
            patch("src.key_service.get_current_key_holder_info", return_value=("Mailbox", "", 0)),
            patch("src.key_service.get_gym_member_id_by_telegram_user_id") as get_member_id,
            patch("src.key_service.change_key_holder") as change_key_holder,
        ):
            result = take_key_from_mailbox("database.sqlite3", None, key_id=1)

        self.assertEqual(TakeFromMailboxStatus.MISSING_TELEGRAM_USER, result.status)
        get_member_id.assert_not_called()
        change_key_holder.assert_not_called()

    def test_take_key_from_mailbox_rejects_unregistered_user(self):
        with (
            patch("src.key_service.get_current_key_holder_info", return_value=("Mailbox", "", 0)),
            patch("src.key_service.get_gym_member_id_by_telegram_user_id", return_value=None),
            patch("src.key_service.change_key_holder") as change_key_holder,
        ):
            result = take_key_from_mailbox("database.sqlite3", 123, key_id=1)

        self.assertEqual(TakeFromMailboxStatus.USER_NOT_REGISTERED, result.status)
        change_key_holder.assert_not_called()


if __name__ == "__main__":
    unittest.main()
