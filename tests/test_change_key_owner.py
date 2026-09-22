import sqlite3
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src import messages
from src.admin_command_handlers import change_key_owner_command_handler
from src.config import DEFAULT_DATABASE_PATH
from src.database import (
    add_gym_member,
    change_key_holder,
    get_key_history,
    get_key_status,
    initialize_database,
    set_key_owner,
)
from src.models import GymMember


class ChangeKeyOwnerCommandTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.message = SimpleNamespace(reply_text=AsyncMock())
        self.update = SimpleNamespace(
            effective_message=self.message,
            effective_user=SimpleNamespace(id=100),
        )
        self.admin = GymMember(10, 100, "Admin", "User", 1234, None, True)
        self.owner = GymMember(20, 200, "New", "Owner", 4321, None, False)
        self.lookup = self.enterContext(patch(
            "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
            side_effect=[self.admin, self.owner],
        ))
        self.set_owner = self.enterContext(patch(
            "src.admin_command_handlers.set_key_owner", return_value=True,
        ))

    async def test_rejects_unauthorized_users(self):
        for requester, reply in (
            (None, messages.AUTH_USER_UNREGISTERED_TEXT),
            (self.owner, messages.ADMIN_COMMAND_FORBIDDEN_TEXT),
        ):
            with self.subTest(requester=requester):
                self.lookup.side_effect = [requester]
                self.message.reply_text.reset_mock()
                await change_key_owner_command_handler(self.update, SimpleNamespace(args=["1", "200"]))
                self.message.reply_text.assert_awaited_once_with(reply)
                self.set_owner.assert_not_called()

    async def test_rejects_invalid_arguments(self):
        for args, reply in (
            ([], messages.ADMIN_CHANGE_KEY_OWNER_USAGE_TEXT),
            (["1"], messages.ADMIN_CHANGE_KEY_OWNER_USAGE_TEXT),
            (["1", "200", "extra"], messages.ADMIN_CHANGE_KEY_OWNER_USAGE_TEXT),
            (["bad", "200"], messages.ADMIN_BAD_VALUE_TEXT),
            (["1", "bad"], messages.ADMIN_BAD_VALUE_TEXT),
            (["0", "200"], messages.ADMIN_BAD_VALUE_TEXT),
            (["-1", "200"], messages.ADMIN_BAD_VALUE_TEXT),
            (["1", "0"], messages.ADMIN_BAD_VALUE_TEXT),
            (["1", "-200"], messages.ADMIN_BAD_VALUE_TEXT),
        ):
            with self.subTest(args=args):
                self.lookup.side_effect = [self.admin]
                self.message.reply_text.reset_mock()
                await change_key_owner_command_handler(self.update, SimpleNamespace(args=args))
                self.message.reply_text.assert_awaited_once_with(reply)
                self.set_owner.assert_not_called()

    async def test_reports_unregistered_owner(self):
        self.lookup.side_effect = [self.admin, None]
        await change_key_owner_command_handler(self.update, SimpleNamespace(args=["1", "200"]))
        self.set_owner.assert_not_called()
        self.message.reply_text.assert_awaited_once_with(
            messages.ADMIN_CHANGE_KEY_OWNER_USER_NOT_REGISTERED_TEXT.format(telegram_user_id=200),
        )

    async def test_reports_missing_key(self):
        self.set_owner.return_value = False
        await change_key_owner_command_handler(self.update, SimpleNamespace(args=["99", "200"]))
        self.message.reply_text.assert_awaited_once_with(messages.KEY_NOT_FOUND_TEXT.format(key_id=99))

    async def test_sets_owner_using_member_id(self):
        await change_key_owner_command_handler(self.update, SimpleNamespace(args=["1", "200"]))
        self.lookup.assert_called_with(DEFAULT_DATABASE_PATH, 200)
        self.set_owner.assert_called_once_with(DEFAULT_DATABASE_PATH, 1, self.owner.id)
        self.message.reply_text.assert_awaited_once_with(
            messages.ADMIN_CHANGE_KEY_OWNER_COMPLETED_TEXT.format(
                key_id=1, member=self.owner.full_name, telegram_user_id=200,
            ),
        )


class SetKeyOwnerTests(unittest.TestCase):
    def setUp(self):
        self.database_path = ":memory:"
        connection = sqlite3.connect(self.database_path)
        self.addCleanup(connection.close)
        self.enterContext(patch("src.database.sqlite3.connect", return_value=connection))
        initialize_database(self.database_path)
        self.holder = add_gym_member(
            self.database_path, 100, "Current", "Holder", 1234, "@holder",
        )
        self.owner = add_gym_member(
            self.database_path, 200, "New", "Owner", 4321, "@owner",
        )
        with sqlite3.connect(self.database_path) as connection:
            cursor = connection.execute(
                "INSERT INTO keys (current_holder_id, owner_member_id, is_active) VALUES (?, ?, 0)",
                (self.holder.id, self.holder.id),
            )
            self.key_id = cursor.lastrowid
        change_key_holder(self.database_path, self.key_id, self.holder.id)

    def test_changes_only_owner_and_preserves_holder_history(self):
        history = get_key_history(self.database_path, self.key_id)
        self.assertTrue(set_key_owner(self.database_path, self.key_id, self.owner.id))
        status = get_key_status(self.database_path, self.key_id)
        self.assertEqual(status.owner, self.owner)
        self.assertEqual(status.current_holder, self.holder)
        self.assertFalse(status.is_active)
        self.assertEqual(get_key_history(self.database_path, self.key_id), history)

    def test_setting_same_owner_succeeds(self):
        self.assertTrue(set_key_owner(self.database_path, self.key_id, self.holder.id))

    def test_returns_false_for_missing_key(self):
        self.assertFalse(set_key_owner(self.database_path, 999, self.owner.id))

    def test_rejects_nonexistent_owner_without_changing_key(self):
        before = get_key_status(self.database_path, self.key_id)
        with self.assertRaises(sqlite3.IntegrityError):
            set_key_owner(self.database_path, self.key_id, 999)
        self.assertEqual(get_key_status(self.database_path, self.key_id), before)


if __name__ == "__main__":
    unittest.main()
