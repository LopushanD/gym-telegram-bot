import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src import admin_command_handlers, bot, handover_flow, messages
from src.command_handlers_utility import process_key_history_records
from src.database import (
    database_connection, initialize_database, populate_test_mailboxes_and_keys,
    get_active_keys, get_current_keyholder_info, get_all_current_keyholders_info,
    get_key_status, get_key_history, change_key_holder, query_key_table,
)
from src.key_service import get_key_label
from src.keyboards import (
    build_key_obtained_mailbox_key_choice_keyboard,
    build_key_obtained_receiver_key_choice_keyboard,
)
from src.models import Key


class KeyNameTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.path = Path(directory) / "keys.sqlite3"
        initialize_database(self.path)
        self.members, self.keys = populate_test_mailboxes_and_keys(self.path)
        self.key_id = self.keys[0]
        with database_connection(self.path) as connection:
            connection.execute("UPDATE keys SET name = ? WHERE id = ?", ("Red", self.key_id))
        self.label = f"{self.key_id} (Red)"

    def test_queries_preserve_key_names_and_support_name_filter(self):
        key = query_key_table(self.path, Key(name="Red"))[0]
        self.assertEqual(self.key_id, key.key_id)
        self.assertEqual(self.label, key.label)
        self.assertEqual("Red", get_active_keys(self.path)[0].name)
        self.assertEqual("Red", get_key_status(self.path, self.key_id)[0].name)
        self.assertEqual("Red", get_current_keyholder_info(self.path, self.key_id).key_name)
        self.assertEqual("Red", get_all_current_keyholders_info(self.path)[0].key_name)
        self.assertEqual(self.label, get_key_label(self.path, self.key_id))
        self.assertEqual("999", get_key_label(self.path, 999))

    def test_status_holder_and_history_include_name(self):
        key, holder, owner = get_key_status(self.path, self.key_id)
        self.assertIn(self.label, messages.key_status_text(key, holder, owner))
        self.assertIn(self.label, messages.current_key_holder_text(
            get_current_keyholder_info(self.path, self.key_id)))
        change_key_holder(self.path, self.key_id, self.members[1])
        records = get_key_history(self.path, self.key_id)
        self.assertEqual("Red", records[0].key.name)
        self.assertIn(self.label, process_key_history_records(records, "\n")[0])
        self.assertIn(self.label, messages.mailbox_receiver_take_prompt(key))

    def test_selection_buttons_include_name_but_keep_numeric_callbacks(self):
        keys = get_active_keys(self.path)
        for builder in (build_key_obtained_mailbox_key_choice_keyboard,
                        build_key_obtained_receiver_key_choice_keyboard):
            button = builder(keys).inline_keyboard[0][0]
            self.assertEqual(self.label, button.text)
            self.assertTrue(button.callback_data.endswith(f":{self.key_id}"))

    async def test_mailbox_confirmation_prompt_resolves_name(self):
        query = SimpleNamespace(data=f"mailbox_receiver_key_choice:{self.key_id}",
                                answer=AsyncMock())
        message = SimpleNamespace(edit_text=AsyncMock())
        with patch.object(bot, "DATABASE_PATH", self.path):
            await bot.handle_key_obtained_from_mailbox_choice(query, message)
        self.assertIn(self.label, message.edit_text.await_args.args[0])

    async def test_admin_activation_reply_includes_name(self):
        message = SimpleNamespace(reply_text=AsyncMock())
        update = SimpleNamespace(effective_message=message,
                                 effective_user=SimpleNamespace(id=123))
        with (
            patch.object(admin_command_handlers, "DATABASE_PATH", self.path),
            patch.object(admin_command_handlers, "_user_is_admin", return_value=True),
        ):
            await admin_command_handlers.activate_key_command_handler(
                update, SimpleNamespace(args=[str(self.key_id)]))
        message.reply_text.assert_awaited_once_with(f"Activated key {self.label}.")

    async def test_missing_handover_reply_includes_name(self):
        message = SimpleNamespace(chat_id=10)
        query = SimpleNamespace(from_user=SimpleNamespace(id=123))
        reply = AsyncMock()
        with patch.object(handover_flow, "DATABASE_PATH", self.path):
            await handover_flow.handle_pending_handover_obtained_backend(
                self.key_id, query, message, reply)
        self.assertIn(self.label, reply.await_args.args[1])

    def test_initialization_preserves_named_keys(self):
        initialize_database(self.path)
        initialize_database(self.path)
        self.assertEqual("Red", get_key_status(self.path, self.key_id)[0].name)

    def test_legacy_migration_preserves_keys_and_history_and_is_repeatable(self):
        legacy = self.path.with_name("legacy.sqlite3")
        with database_connection(legacy) as connection:
            connection.executescript("""
                CREATE TABLE keys (id INTEGER PRIMARY KEY, current_holder_id INTEGER,
                                   owner_member_id INTEGER, is_active INTEGER);
                INSERT INTO keys VALUES (7, 10, 20, 1);
                CREATE TABLE key_holder_history (event_id INTEGER PRIMARY KEY,
                    key_id INTEGER, holder_id INTEGER, taken_at TIMESTAMP);
                INSERT INTO key_holder_history VALUES (1, 7, 10, '2026-01-01 12:00:00');
            """)
        initialize_database(legacy)
        initialize_database(legacy)
        with database_connection(legacy) as connection:
            self.assertEqual((7, 10, 20, 1, "Unnamed"),
                             connection.execute("SELECT * FROM keys").fetchone())
            self.assertEqual((1, 7, 10, "2026-01-01 12:00:00"),
                             connection.execute("SELECT * FROM key_holder_history").fetchone())
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("UPDATE keys SET name = NULL")
