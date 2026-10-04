import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.key_service import TakeFromMailboxStatus, take_key_from_mailbox
from src.models import GymMember, Key


class TakeFromMailboxTests(unittest.TestCase):
    database_path = "database.sqlite3"

    def test_take_key_from_mailbox_updates_holder_to_member(self):
        mailbox = GymMember(id=7, name="Key", surname="Mailbox")
        with (
            patch("src.key_service.get_gym_member_id_by_telegram_user_id", return_value=42),
            patch(
                "src.key_service.get_key_status",
                return_value=(Key(1, 7, 7, True), mailbox, mailbox),
            ) as get_key_status,
            patch("src.key_service.change_key_holder") as change_key_holder,
        ):
            result = take_key_from_mailbox(self.database_path, 123, key_id=1)

        self.assertEqual(TakeFromMailboxStatus.TAKEN, result.status)
        get_key_status.assert_called_once_with(self.database_path, 1)
        change_key_holder.assert_called_once_with(self.database_path, 1, 42)

    def test_take_key_from_mailbox_rejects_key_held_by_someone_else(self):
        mailbox = GymMember(id=7)
        holder = GymMember(id=8)
        with (
            patch("src.key_service.get_gym_member_id_by_telegram_user_id", return_value=42),
            patch(
                "src.key_service.get_key_status",
                return_value=(Key(1, 8, 7, True), holder, mailbox),
            ),
            patch("src.key_service.change_key_holder") as change_key_holder,
        ):
            result = take_key_from_mailbox(self.database_path, 123, key_id=1)

        self.assertEqual(TakeFromMailboxStatus.KEY_NOT_IN_MAILBOX, result.status)
        change_key_holder.assert_not_called()

    def test_take_key_from_mailbox_rejects_missing_key(self):
        with (
            patch("src.key_service.get_gym_member_id_by_telegram_user_id", return_value=42),
            patch("src.key_service.get_key_status", return_value=(None, None, None)),
            patch("src.key_service.change_key_holder") as change_key_holder,
        ):
            result = take_key_from_mailbox(self.database_path, 123, key_id=99)

        self.assertEqual(TakeFromMailboxStatus.KEY_NOT_FOUND, result.status)
        change_key_holder.assert_not_called()

    def test_take_key_from_mailbox_rejects_inactive_key_from_old_button(self):
        mailbox = GymMember(id=7)
        with (
            patch("src.key_service.get_gym_member_id_by_telegram_user_id", return_value=42),
            patch(
                "src.key_service.get_key_status",
                return_value=(Key(1, 7, 7, False), mailbox, mailbox),
            ),
            patch("src.key_service.change_key_holder") as change_key_holder,
        ):
            result = take_key_from_mailbox(self.database_path, 123, key_id=1)

        self.assertEqual(TakeFromMailboxStatus.KEY_NOT_FOUND, result.status)
        change_key_holder.assert_not_called()

    def test_take_key_from_mailbox_rejects_missing_telegram_user(self):
        with (
            patch("src.key_service.get_gym_member_id_by_telegram_user_id") as get_member_id,
            patch("src.key_service.get_key_status") as get_key_status,
            patch("src.key_service.change_key_holder") as change_key_holder,
        ):
            result = take_key_from_mailbox(self.database_path, None, key_id=1)

        self.assertEqual(TakeFromMailboxStatus.MISSING_TELEGRAM_USER, result.status)
        get_member_id.assert_not_called()
        get_key_status.assert_not_called()
        change_key_holder.assert_not_called()

    def test_take_key_from_mailbox_rejects_unregistered_user(self):
        with (
            patch("src.key_service.get_gym_member_id_by_telegram_user_id", return_value=None),
            patch("src.key_service.get_key_status") as get_key_status,
            patch("src.key_service.change_key_holder") as change_key_holder,
        ):
            result = take_key_from_mailbox(self.database_path, 123, key_id=1)

        self.assertEqual(TakeFromMailboxStatus.USER_NOT_REGISTERED, result.status)
        get_key_status.assert_not_called()
        change_key_holder.assert_not_called()


if __name__ == "__main__":
    unittest.main()
