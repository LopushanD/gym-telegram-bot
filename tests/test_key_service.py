import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.key_service import (
    HandoverStatus,
    get_key_holder,
    can_start_key_handover,
    user_currently_holds_key,
)


class KeyServiceTests(unittest.TestCase):
    def test_get_key_holder_returns_domain_object(self):
        with patch(
            "src.key_service.get_current_key_holder_info",
            return_value=("Dima", "Ivanov", 1234, "@dima", "+49123456789"),
        ):
            holder = get_key_holder("database.sqlite3", key_id=1)

        self.assertEqual("Dima", holder.name)
        self.assertEqual("Ivanov", holder.surname)
        self.assertEqual(1234, holder.room_number)
        self.assertEqual("@dima", holder.telegram_name)
        self.assertEqual("+49123456789", holder.phone_number)

    def test_get_key_holder_returns_none_when_key_is_missing(self):
        with patch("src.key_service.get_current_key_holder_info", return_value=None):
            holder = get_key_holder("database.sqlite3", key_id=1)

        self.assertIsNone(holder)

    def test_user_currently_holds_key_checks_holder_by_telegram_id(self):
        with patch(
            "src.key_service.get_current_key_holder_info",
            return_value=("Dima", "Ivanov", 1234, "@dima", "+49123456789"),
        ) as get_current_key_holder_info:
            is_holder = user_currently_holds_key("database.sqlite3", 123, key_id=1)

        self.assertTrue(is_holder)
        get_current_key_holder_info.assert_called_once_with(
            "database.sqlite3",
            1,
            123,
        )

    def test_user_currently_holds_key_returns_false_without_telegram_id(self):
        with patch("src.key_service.get_current_key_holder_info") as get_current_key_holder_info:
            is_holder = user_currently_holds_key("database.sqlite3", None, key_id=1)

        self.assertFalse(is_holder)
        get_current_key_holder_info.assert_not_called()

    def test_start_key_handover_returns_ready_for_current_holder(self):
        with patch("src.key_service.user_currently_holds_key", return_value=True):
            result = can_start_key_handover("database.sqlite3", 123, key_id=1)

        self.assertEqual(HandoverStatus.READY, result.status)

    def test_start_key_handover_rejects_non_holder(self):
        with patch("src.key_service.user_currently_holds_key", return_value=False):
            result = can_start_key_handover("database.sqlite3", 123, key_id=1)

        self.assertEqual(HandoverStatus.NOT_CURRENT_HOLDER, result.status)


if __name__ == "__main__":
    unittest.main()
