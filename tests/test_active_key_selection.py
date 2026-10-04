import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src import bot, messages
from src.admin_command_handlers import key_status_command_handler
from src.database import (
    database_connection,
    get_active_keys,
    initialize_database,
    set_key_active,
)
from src.keyboards import (
    RECEIVER_HANDOVER_KEY_CHOICE_CALLBACK_PREFIX,
    RECEIVER_KEY_HANDOVER_CANCEL_CALLBACK,
    RECEIVER_MAILBOX_KEY_CHOICE_CALLBACK_PREFIX,
    RECEIVER_MAILBOX_KEY_OBTAINED_CANCEL_CALLBACK,
)
from src.models import Key
from src.key_service import TakeFromMailboxStatus, take_key_from_mailbox


class ActiveKeySelectionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.database_path = Path(directory) / "test.sqlite3"
        initialize_database(self.database_path)
        with database_connection(self.database_path) as connection:
            connection.executemany(
                """INSERT INTO gym_members
                   (id, telegram_user_id, name, surname, room_number, is_admin)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [(1, 100, "Key", "Owner", 101, 0),
                 (2, 200, "Current", "Holder", 202, 1)],
            )
            connection.executemany(
                """INSERT INTO keys
                   (id, current_holder_id, owner_member_id, is_active)
                   VALUES (?, 2, 1, ?)""",
                [(2, 1), (5, 0), (9, 1)],
            )

    def test_active_query_preserves_ids_and_member_references(self):
        self.assertCountEqual(
            [Key(2, 2, 1, True), Key(9, 2, 1, True)],
            get_active_keys(self.database_path),
        )

    def test_active_query_returns_empty_for_empty_table(self):
        with database_connection(self.database_path) as connection:
            connection.execute("DELETE FROM keys")
        self.assertEqual([], get_active_keys(self.database_path))

    def test_activation_changes_query_results_without_renumbering(self):
        set_key_active(self.database_path, 2, False)
        set_key_active(self.database_path, 5, True)
        self.assertCountEqual([5, 9], [key.key_id for key in get_active_keys(self.database_path)])

    async def test_both_pickup_menus_use_only_existing_active_ids(self):
        cases = (
            (bot.handle_key_obtained, RECEIVER_HANDOVER_KEY_CHOICE_CALLBACK_PREFIX,
             RECEIVER_KEY_HANDOVER_CANCEL_CALLBACK),
            (bot.handle_key_obtained_from_mailbox, RECEIVER_MAILBOX_KEY_CHOICE_CALLBACK_PREFIX,
             RECEIVER_MAILBOX_KEY_OBTAINED_CANCEL_CALLBACK),
        )
        for handler, prefix, cancel in cases:
            with self.subTest(handler=handler.__name__):
                message = SimpleNamespace(edit_text=AsyncMock())
                query = SimpleNamespace(
                    answer=AsyncMock(), from_user=SimpleNamespace(id=200)
                )
                with patch.object(bot, "DATABASE_PATH", self.database_path):
                    await handler(query, message)
                args, kwargs = message.edit_text.await_args
                self.assertEqual((messages.KEY_CHOICE_PROMPT,), args)
                buttons = [button for row in kwargs["reply_markup"].inline_keyboard for button in row]
                self.assertCountEqual(
                    [("2", f"{prefix}:2"), ("9", f"{prefix}:9"), ("Cancel", cancel)],
                    [(button.text, button.callback_data) for button in buttons],
                )

    async def test_no_active_keys_leaves_a_working_cancel_button(self):
        for key_id in (2, 9):
            set_key_active(self.database_path, key_id, False)
        cases = (
            (bot.handle_key_obtained, RECEIVER_KEY_HANDOVER_CANCEL_CALLBACK),
            (bot.handle_key_obtained_from_mailbox, RECEIVER_MAILBOX_KEY_OBTAINED_CANCEL_CALLBACK),
        )
        for handler, cancel in cases:
            with self.subTest(handler=handler.__name__):
                message = SimpleNamespace(edit_text=AsyncMock())
                with patch.object(bot, "DATABASE_PATH", self.database_path):
                    await handler(
                        SimpleNamespace(
                            answer=AsyncMock(), from_user=SimpleNamespace(id=200)
                        ),
                        message,
                    )
                rows = message.edit_text.await_args.kwargs["reply_markup"].inline_keyboard
                self.assertEqual(1, len(rows))
                self.assertEqual(cancel, rows[0][0].callback_data)

    def test_mailbox_pickup_records_active_key_and_rejects_invalid_choices(self):
        with database_connection(self.database_path) as connection:
            connection.execute("UPDATE keys SET current_holder_id = 1 WHERE id = 2")

        self.assertEqual(
            TakeFromMailboxStatus.KEY_NOT_FOUND,
            take_key_from_mailbox(self.database_path, 200, 5).status,
        )
        self.assertEqual(
            TakeFromMailboxStatus.KEY_NOT_IN_MAILBOX,
            take_key_from_mailbox(self.database_path, 200, 9).status,
        )
        self.assertEqual(
            TakeFromMailboxStatus.KEY_NOT_FOUND,
            take_key_from_mailbox(self.database_path, 200, 999).status,
        )
        self.assertEqual(
            TakeFromMailboxStatus.TAKEN,
            take_key_from_mailbox(self.database_path, 200, 2).status,
        )

        with database_connection(self.database_path) as connection:
            keys = connection.execute(
                "SELECT id, current_holder_id FROM keys ORDER BY id"
            ).fetchall()
            history = connection.execute(
                "SELECT key_id, holder_id FROM key_holder_history"
            ).fetchall()

        self.assertEqual([(2, 2), (5, 2), (9, 2)], keys)
        self.assertEqual([(2, 2)], history)

    async def test_status_command_formats_real_holder_and_owner_for_inactive_key(self):
        message = SimpleNamespace(reply_text=AsyncMock())
        update = SimpleNamespace(effective_message=message, effective_user=SimpleNamespace(id=200))
        with patch("src.admin_command_handlers.DATABASE_PATH", self.database_path):
            await key_status_command_handler(update, SimpleNamespace(args=["5"]))
        text = message.reply_text.await_args.args[0]
        for expected in ("Key ID: 5", "Active: no", "Current Holder", "Key Owner",
                         "Gym member ID: 2", "Gym member ID: 1", "is admin: True", "is admin: False"):
            self.assertIn(expected, text)

    async def test_status_command_handles_missing_key_without_unpacking_error(self):
        message = SimpleNamespace(reply_text=AsyncMock())
        update = SimpleNamespace(effective_message=message, effective_user=SimpleNamespace(id=200))
        with patch("src.admin_command_handlers.DATABASE_PATH", self.database_path):
            await key_status_command_handler(update, SimpleNamespace(args=["999"]))
        message.reply_text.assert_awaited_once_with(messages.KEY_NOT_ACTIVE_TEXT.format(key_id=999))
