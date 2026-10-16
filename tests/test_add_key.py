import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from src import bot, messages
from src.admin_command_handlers import add_key_command_handler
from src.admin_commands import ADD_KEY_ADMIN_COMMAND, load_command_documentation
from src.config import DATABASE_PATH
from src.database import add_key, database_connection, get_key_history, get_key_status, initialize_database
from src.models import GymMember


class AddKeyDatabaseTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.path = Path(directory) / "keys.sqlite3"
        initialize_database(self.path)
        with database_connection(self.path) as connection:
            connection.execute(
                """INSERT INTO gym_members (id, telegram_user_id, name, surname, room_number)
                   VALUES (20, 200, 'Ada', 'Owner', 202)"""
            )
            connection.execute(
                """INSERT INTO keys (id, name, current_holder_id, owner_member_id, is_in_mailbox)
                   VALUES (7, 'Blue', 20, 20, 1)"""
            )
            connection.execute(
                """INSERT INTO key_holder_history (key_id, holder_id, taken_at, put_into_mailbox)
                   VALUES (7, 20, '2026-10-01 12:00:00', 1)"""
            )

    def test_adds_one_inactive_key_with_defaults_and_preserves_existing_data(self):
        previous_history = get_key_history(self.path, 7)

        key_id = add_key(self.path, 20)

        key, holder, owner = get_key_status(self.path, key_id)
        self.assertEqual(8, key_id)
        self.assertEqual("Unnamed", key.name)
        self.assertIs(key.is_active, False)
        self.assertIs(key.is_in_mailbox, False)
        self.assertEqual(20, key.current_holder_id)
        self.assertEqual(20, key.owner_member_id)
        self.assertEqual(holder, owner)
        self.assertEqual([], get_key_history(self.path, key_id))
        self.assertEqual(previous_history, get_key_history(self.path, 7))
        with database_connection(self.path) as connection:
            self.assertEqual(2, connection.execute("SELECT COUNT(*) FROM keys").fetchone()[0])
            self.assertTrue(connection.execute("SELECT created_at FROM keys WHERE id = ?", (key_id,)).fetchone()[0])
            self.assertEqual(
                {"gym_members", "keys", "key_holder_history"},
                {row[0] for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                )},
            )
            self.assertEqual([], connection.execute("PRAGMA foreign_key_check").fetchall())

    def test_preserves_custom_name_and_creates_a_new_key_on_each_call(self):
        first_id = add_key(self.path, 20, "  Owner's spare  ")
        second_id = add_key(self.path, 20, "Owner's spare")

        self.assertNotEqual(first_id, second_id)
        for key_id in (first_id, second_id):
            self.assertEqual("Owner's spare", get_key_status(self.path, key_id)[0].name)
        initialize_database(self.path)
        with database_connection(self.path) as connection:
            self.assertEqual(3, connection.execute("SELECT COUNT(*) FROM keys").fetchone()[0])

    def test_rejects_invalid_values_and_missing_owner_without_creating_keys(self):
        for owner_id, name, error in (
            (0, None, ValueError), (-1, None, ValueError),
            (20, "", ValueError), (20, "  ", ValueError),
            (999, None, sqlite3.IntegrityError),
        ):
            with self.subTest(owner_id=owner_id, name=name):
                with self.assertRaises(error):
                    add_key(self.path, owner_id, name)
        with database_connection(self.path) as connection:
            self.assertEqual([(7,)], connection.execute("SELECT id FROM keys").fetchall())


class AddKeyCommandTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.message = SimpleNamespace(reply_text=AsyncMock())
        self.update = SimpleNamespace(
            effective_message=self.message, effective_user=SimpleNamespace(id=100),
        )
        self.admin = GymMember(id=10, telegram_user_id=100, is_admin=True)
        self.owner = GymMember(id=20, telegram_user_id=200, name="Ada", surname="Owner")
        self.lookup = self.enterContext(patch(
            "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
            side_effect=[self.admin, self.owner],
        ))
        self.add_key = self.enterContext(patch("src.admin_command_handlers.add_key", return_value=8))
        self.key_label = self.enterContext(patch(
            "src.admin_command_handlers.get_key_label", return_value="8 (Unnamed)",
        ))

    async def test_rejects_unregistered_and_non_admin_requesters(self):
        for member, reply in (
            (None, messages.AUTH_USER_UNREGISTERED_TEXT),
            (self.owner, messages.ADMIN_COMMAND_FORBIDDEN_TEXT),
        ):
            with self.subTest(member=member):
                self.lookup.side_effect = [member]
                self.message.reply_text.reset_mock()
                await add_key_command_handler(self.update, SimpleNamespace(args=["200"]))
                self.message.reply_text.assert_awaited_once_with(reply)
                self.add_key.assert_not_called()

    async def test_help_options_show_documentation_without_adding_a_key(self):
        for option in ("-h", "--help"):
            with self.subTest(option=option):
                self.lookup.side_effect = [self.admin]
                self.message.reply_text.reset_mock()
                await add_key_command_handler(self.update, SimpleNamespace(args=["bad-id", option]))
                self.message.reply_text.assert_awaited_once_with(
                    load_command_documentation(ADD_KEY_ADMIN_COMMAND), parse_mode="MarkdownV2",
                )
                self.add_key.assert_not_called()

    async def test_missing_arguments_show_usage(self):
        self.lookup.side_effect = [self.admin]

        await add_key_command_handler(self.update, SimpleNamespace())

        self.message.reply_text.assert_awaited_once_with(messages.ADMIN_ADD_KEY_USAGE_TEXT)
        self.add_key.assert_not_called()

    async def test_rejects_invalid_owner_ids_and_blank_names(self):
        for args in (["bad"], ["0"], ["-200"], ["200", ""], ["200", " ", " "]):
            with self.subTest(args=args):
                self.lookup.side_effect = [self.admin]
                self.message.reply_text.reset_mock()
                await add_key_command_handler(self.update, SimpleNamespace(args=args))
                self.message.reply_text.assert_awaited_once_with(messages.ADMIN_BAD_VALUE_TEXT)
                self.add_key.assert_not_called()

    async def test_reports_unregistered_owner(self):
        self.lookup.side_effect = [self.admin, None]

        await add_key_command_handler(self.update, SimpleNamespace(args=["200"]))

        self.message.reply_text.assert_awaited_once_with(
            messages.ADMIN_ADD_KEY_USER_NOT_REGISTERED_TEXT.format(telegram_user_id=200),
        )
        self.add_key.assert_not_called()

    async def test_creates_key_using_member_id_and_reports_generated_key(self):
        await add_key_command_handler(self.update, SimpleNamespace(args=["200"]))

        self.lookup.assert_called_with(DATABASE_PATH, 200)
        self.add_key.assert_called_once_with(DATABASE_PATH, self.owner.id, name=None)
        self.key_label.assert_called_once_with(DATABASE_PATH, 8)
        self.message.reply_text.assert_awaited_once_with(
            messages.ADMIN_ADD_KEY_COMPLETED_TEXT.format(
                key_id="8 (Unnamed)", member="Ada Owner", telegram_user_id=200,
            ),
        )

    async def test_accepts_multiword_key_name(self):
        self.key_label.return_value = "8 (Red spare)"

        await add_key_command_handler(self.update, SimpleNamespace(args=["200", "Red", "spare"]))

        self.add_key.assert_called_once_with(DATABASE_PATH, self.owner.id, name="Red spare")
        self.assertIn("8 (Red spare)", self.message.reply_text.await_args.args[0])

    async def test_database_failure_is_not_reported_as_success(self):
        self.add_key.side_effect = sqlite3.OperationalError("database unavailable")

        with self.assertRaisesRegex(sqlite3.OperationalError, "database unavailable"):
            await add_key_command_handler(self.update, SimpleNamespace(args=["200"]))

        self.message.reply_text.assert_not_called()


class AddKeyIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_admin_command_persists_key_for_selected_owner(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        path = Path(directory) / "keys.sqlite3"
        initialize_database(path)
        with database_connection(path) as connection:
            connection.executemany(
                """INSERT INTO gym_members (id, telegram_user_id, name, surname, room_number, is_admin)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [(10, 100, "Admin", "User", 101, 1), (20, 200, "Ada", "Owner", 202, 0)],
            )
        message = SimpleNamespace(reply_text=AsyncMock())
        update = SimpleNamespace(effective_message=message, effective_user=SimpleNamespace(id=100))

        with patch("src.admin_command_handlers.DATABASE_PATH", path):
            await add_key_command_handler(update, SimpleNamespace(args=["200", "Red", "spare"]))

        key, holder, owner = get_key_status(path, 1)
        self.assertEqual((20, 20, "Red spare", False, False), (
            key.current_holder_id, key.owner_member_id, key.name, key.is_active, key.is_in_mailbox,
        ))
        self.assertEqual(holder, owner)
        self.assertEqual([], get_key_history(path, 1))
        message.reply_text.assert_awaited_once_with(
            "Added inactive key 1 (Red spare), owned and held by Ada Owner (Telegram ID 200)."
        )


class AddKeyRegistrationTests(unittest.TestCase):
    def test_bot_registers_add_key_handler(self):
        application = MagicMock()
        builder = MagicMock()
        for method in ("token", "concurrent_updates", "read_timeout", "write_timeout"):
            getattr(builder, method).return_value = builder
        builder.build.return_value = application
        with (
            patch.object(bot, "initialize_database"),
            patch.object(bot.Application, "builder", return_value=builder),
            patch("builtins.print"),
        ):
            bot.main()

        handlers = [call.args[0] for call in application.add_handler.call_args_list]
        handler = next(handler for handler in handlers if ADD_KEY_ADMIN_COMMAND in getattr(handler, "commands", ()))
        self.assertIs(handler.callback, add_key_command_handler)
