import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.key_service import (
    ReturnToMailboxStatus,
    return_key_to_mailbox,
)


class ReturnToMailboxTests(unittest.TestCase):
    def test_return_key_to_mailbox_updates_holder_to_mailbox_member(self):
        with (
            patch("src.key_service.user_currently_holds_key", return_value=True),
            patch("src.key_service.change_key_holder") as change_key_holder,
        ):
            result = return_key_to_mailbox("database.sqlite3", 123, key_id=1)

        self.assertEqual(ReturnToMailboxStatus.RETURNED, result.status)
        change_key_holder.assert_called_once_with("database.sqlite3", 1, 1)

    def test_return_key_to_mailbox_rejects_non_holder(self):
        with (
            patch("src.key_service.user_currently_holds_key", return_value=False),
            patch("src.key_service.change_key_holder") as change_key_holder,
        ):
            result = return_key_to_mailbox("database.sqlite3", 456, key_id=1)

        self.assertEqual(ReturnToMailboxStatus.NOT_CURRENT_HOLDER, result.status)
        change_key_holder.assert_not_called()


if __name__ == "__main__":
    unittest.main()
