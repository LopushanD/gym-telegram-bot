import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src import messages
from src.admin_command_handlers import set_admin_command_handler
from src.admin_commands import load_command_documentation
from src.config import DATABASE_PATH
from src.database import (
    add_gym_member,
    database_connection,
    get_gym_member_by_telegram_user_id,
    initialize_database,
    set_admin,
)
from src.models import GymMember


class SetAdminCommandTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.message = SimpleNamespace(reply_text=AsyncMock())
        self.update = SimpleNamespace(
            effective_message=self.message, effective_user=SimpleNamespace(id=100),
        )
        self.lookup = self.enterContext(patch(
            "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
            return_value=GymMember(telegram_user_id=100, is_admin=True),
        ))
        self.set_admin = self.enterContext(patch(
            "src.admin_command_handlers.set_admin",
            return_value=[GymMember(telegram_user_id=200, name="Alan", surname="Turing",
                                   room_number=102, telegram_name="@alan", is_admin=True)],
        ))

    async def test_rejects_unregistered_and_non_admin_requesters(self):
        for member, reply in (
            (None, messages.AUTH_USER_UNREGISTERED_TEXT),
            (GymMember(is_admin=False), messages.ADMIN_COMMAND_FORBIDDEN_TEXT),
        ):
            with self.subTest(member=member):
                self.lookup.return_value = member
                await set_admin_command_handler(self.update, SimpleNamespace(args=["200", "True"]))
                self.message.reply_text.assert_awaited_with(reply)
                self.set_admin.assert_not_called()

    async def test_grants_and_revokes_with_case_insensitive_values(self):
        for value, expected in (("True", True), ("False", False), ("TRUE", True), ("false", False)):
            with self.subTest(value=value):
                self.set_admin.reset_mock()
                self.message.reply_text.reset_mock()
                self.set_admin.return_value[0].is_admin = expected
                await set_admin_command_handler(self.update, SimpleNamespace(args=["200", value]))
                self.set_admin.assert_called_once_with(DATABASE_PATH, 200, expected)
                self.message.reply_text.assert_awaited_once_with(
                    messages.ADMIN_SET_ADMIN_COMPLETED_TEXT.format(
                        member="Name: Alan Turing\nRoom: 102\nTelegram username: @alan\n"
                               f"is admin: {expected}"
                    )
                )

    async def test_rejects_invalid_arguments_without_writing(self):
        for args in ([], ["200"], ["200", "True", "extra"]):
            await set_admin_command_handler(self.update, SimpleNamespace(args=args))
            self.message.reply_text.assert_awaited_with(messages.ADMIN_SET_ADMIN_USAGE_TEXT)
        for args in (["abc", "True"], ["0", "True"], ["-1", "False"], ["1.5", "True"],
                     ["200", "yes"], ["200", "0"], ["200", "1"], ["200", "True/False"]):
            with self.subTest(args=args):
                await set_admin_command_handler(self.update, SimpleNamespace(args=args))
                self.message.reply_text.assert_awaited_with(messages.ADMIN_SET_ADMIN_BAD_VALUE_TEXT)
        self.set_admin.assert_not_called()

    async def test_reports_missing_target(self):
        self.set_admin.return_value = []
        await set_admin_command_handler(self.update, SimpleNamespace(args=["200", "True"]))
        self.message.reply_text.assert_awaited_once_with(
            messages.ADMIN_SET_ADMIN_NOT_FOUND_TEXT.format(telegram_user_id=200)
        )

    async def test_help_does_not_write(self):
        for option in ("-h", "--help"):
            await set_admin_command_handler(self.update, SimpleNamespace(args=[option]))
            self.message.reply_text.assert_awaited_with(
                load_command_documentation("setadmin"), parse_mode="MarkdownV2",
            )
        self.set_admin.assert_not_called()

    async def test_admin_can_revoke_own_rights(self):
        self.set_admin.return_value = [GymMember(telegram_user_id=100, is_admin=False)]
        await set_admin_command_handler(self.update, SimpleNamespace(args=["100", "False"]))
        self.set_admin.assert_called_once_with(DATABASE_PATH, 100, False)


class SetAdminDatabaseTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.database_path = Path(directory) / "test.sqlite3"
        initialize_database(self.database_path)
        add_gym_member(self.database_path, GymMember(telegram_user_id=100, name="Ada", surname="Lovelace", room_number=101, telegram_name="@ada"))
        add_gym_member(self.database_path, GymMember(telegram_user_id=200, name="Alan", surname="Turing", room_number=102, telegram_name="@alan"))

    def test_persists_both_values_and_preserves_other_data(self):
        unchanged_fields_query = """
            SELECT id, telegram_user_id, name, surname, room_number, created_at,
                   telegram_name, suspended_until, deleted_at
            FROM gym_members ORDER BY id
        """
        with database_connection(self.database_path) as connection:
            before = connection.execute(unchanged_fields_query).fetchall()
        for value in (True, True, False, False):
            with self.subTest(value=value):
                members = set_admin(self.database_path, 100, value)
                self.assertEqual(1, len(members))
                self.assertEqual(100, members[0].telegram_user_id)
                self.assertIs(value, members[0].is_admin)
                persisted = get_gym_member_by_telegram_user_id(self.database_path, 100)
                self.assertEqual([persisted], members)
                self.assertIs(value, persisted.is_admin)
                self.assertFalse(get_gym_member_by_telegram_user_id(self.database_path, 200).is_admin)
                with database_connection(self.database_path) as connection:
                    after = connection.execute(unchanged_fields_query).fetchall()
                self.assertEqual(before, after)

    def test_missing_member_is_not_created(self):
        self.assertEqual([], set_admin(self.database_path, 999, True))
        self.assertIsNone(get_gym_member_by_telegram_user_id(self.database_path, 999))


class SetAdminIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_self_revocation_is_persisted_and_blocks_next_admin_command(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        database_path = Path(directory) / "test.sqlite3"
        initialize_database(database_path)
        add_gym_member(database_path, GymMember(telegram_user_id=100, name="Ada", surname="Lovelace", room_number=101, telegram_name="@ada"))
        set_admin(database_path, 100, True)
        message = SimpleNamespace(reply_text=AsyncMock())
        update = SimpleNamespace(effective_message=message, effective_user=SimpleNamespace(id=100))

        with patch("src.admin_command_handlers.DATABASE_PATH", database_path):
            await set_admin_command_handler(update, SimpleNamespace(args=["100", "False"]))
            message.reply_text.assert_awaited_once_with(
                messages.ADMIN_SET_ADMIN_COMPLETED_TEXT.format(
                    member="Name: Ada Lovelace\nRoom: 101\nTelegram username: @ada\nis admin: False"
                )
            )
            self.assertFalse(get_gym_member_by_telegram_user_id(database_path, 100).is_admin)
            message.reply_text.reset_mock()
            await set_admin_command_handler(update, SimpleNamespace(args=["100", "True"]))
            message.reply_text.assert_awaited_once_with(messages.ADMIN_COMMAND_FORBIDDEN_TEXT)
            self.assertFalse(get_gym_member_by_telegram_user_id(database_path, 100).is_admin)


if __name__ == "__main__":
    unittest.main()
