import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.key_service import (
    ConfirmKeyStatus,
    HandoverStatus,
    confirm_key_obtained,
    get_key_holder,
    start_key_handover,
    user_currently_holds_key,
)


class KeyServiceTests(unittest.TestCase):
    def test_get_key_holder_returns_domain_object(self):
        with patch(
            "src.key_service.get_current_key_holder",
            return_value=("Dima", "Ivanov", 1234),
        ):
            holder = get_key_holder("database.sqlite3", key_id=1)

        self.assertEqual("Dima", holder.name)
        self.assertEqual("Ivanov", holder.surname)
        self.assertEqual(1234, holder.room_number)

    def test_get_key_holder_returns_none_when_key_is_missing(self):
        with patch("src.key_service.get_current_key_holder", return_value=None):
            holder = get_key_holder("database.sqlite3", key_id=1)

        self.assertIsNone(holder)

    def test_user_currently_holds_key_checks_holder_by_telegram_id(self):
        with patch(
            "src.key_service.get_current_key_holder",
            return_value=("Dima", "Ivanov", 1234),
        ) as get_current_key_holder:
            is_holder = user_currently_holds_key("database.sqlite3", 123, key_id=1)

        self.assertTrue(is_holder)
        get_current_key_holder.assert_called_once_with(
            "database.sqlite3",
            key_id=1,
            telegram_user_id=123,
        )

    def test_user_currently_holds_key_returns_false_without_telegram_id(self):
        with patch("src.key_service.get_current_key_holder") as get_current_key_holder:
            is_holder = user_currently_holds_key("database.sqlite3", None, key_id=1)

        self.assertFalse(is_holder)
        get_current_key_holder.assert_not_called()

    def test_start_key_handover_returns_ready_for_current_holder(self):
        with patch("src.key_service.user_currently_holds_key", return_value=True):
            result = start_key_handover("database.sqlite3", 123, key_id=1)

        self.assertEqual(HandoverStatus.READY, result.status)

    def test_start_key_handover_rejects_non_holder(self):
        with patch("src.key_service.user_currently_holds_key", return_value=False):
            result = start_key_handover("database.sqlite3", 123, key_id=1)

        self.assertEqual(HandoverStatus.NOT_CURRENT_HOLDER, result.status)

    def test_confirm_key_obtained_updates_holder(self):
        with (
            patch(
                "src.key_service.get_gym_member_id_by_telegram_user_id",
                return_value=42,
            ),
            patch("src.key_service.change_key_holder") as change_key_holder,
        ):
            result = confirm_key_obtained("database.sqlite3", 123, key_id=1)

        self.assertEqual(ConfirmKeyStatus.CONFIRMED, result.status)
        change_key_holder.assert_called_once_with("database.sqlite3", 1, 42)

    def test_confirm_key_obtained_rejects_missing_telegram_user(self):
        with patch("src.key_service.change_key_holder") as change_key_holder:
            result = confirm_key_obtained("database.sqlite3", None, key_id=1)

        self.assertEqual(ConfirmKeyStatus.MISSING_TELEGRAM_USER, result.status)
        change_key_holder.assert_not_called()

    def test_confirm_key_obtained_rejects_unregistered_user(self):
        with (
            patch(
                "src.key_service.get_gym_member_id_by_telegram_user_id",
                return_value=None,
            ),
            patch("src.key_service.change_key_holder") as change_key_holder,
        ):
            result = confirm_key_obtained("database.sqlite3", 123, key_id=1)

        self.assertEqual(ConfirmKeyStatus.USER_NOT_REGISTERED, result.status)
        change_key_holder.assert_not_called()


if __name__ == "__main__":
    unittest.main()
