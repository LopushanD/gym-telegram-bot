import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src import admin_command_handlers, bot, bot_replies, handover_flow, messages
from src.database import change_key_holder, database_connection, initialize_database, set_key_active
from src.keyboards import (
    GET_STARTING_MESSAGE_CALLBACK,
    HOLDER_KEY_HANDOVER_CALLBACK,
    HOLDER_KEY_HANDOVER_CANCEL_CALLBACK,
    HOLDER_KEY_RETURN_MAILBOX_CALLBACK,
    HOLDER_KEY_RETURN_MAILBOX_CANCEL_CALLBACK,
    RECEIVER_KEY_INFO_CALLBACK,
    RECEIVER_MAILBOX_KEY_OBTAINED_CANCEL_CALLBACK,
    RECEIVER_MAILBOX_KEY_OBTAINED_CALLBACK,
    handover_key_choice_callback,
    handover_key_obtained_confirm_callback,
    mailbox_key_choice_callback,
    mailbox_key_obtained_confirm_callback,
    mailbox_key_return_choice_callback,
    mailbox_key_return_confirm_callback,
)


class KeyLocationFlowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.path = Path(directory) / "keys.sqlite3"
        initialize_database(self.path)
        with database_connection(self.path) as connection:
            connection.executemany(
                """INSERT INTO gym_members
                   (id, telegram_user_id, name, surname, room_number, telegram_name, is_admin)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [(1, 100, "Ada", "Owner", 101, "@ada", 1),
                 (2, 200, "Ben", "Borrower", 202, "@ben", 0),
                 (3, 300, "Cara", "Receiver", 303, "@cara", 0)],
            )
            connection.execute(
                """INSERT INTO keys (id, name, current_holder_id, owner_member_id, is_in_mailbox)
                   VALUES (1, 'Red', 2, 1, 0)"""
            )
        for module in (bot, bot_replies, handover_flow, admin_command_handlers):
            self.enterContext(patch.object(module, "DATABASE_PATH", self.path))
        self.addCleanup(handover_flow.cancel_pending_handover, 1)

    async def press(self, telegram_user_id, callback, message=None):
        if message is None:
            message = SimpleNamespace(edit_text=AsyncMock(), chat_id=telegram_user_id, message_id=10)
        query = SimpleNamespace(
            answer=AsyncMock(), data=callback, message=message,
            from_user=SimpleNamespace(id=telegram_user_id),
        )
        await bot.callback_query_handler(SimpleNamespace(callback_query=query), SimpleNamespace())
        query.answer.assert_awaited_once_with()
        return message

    async def give_key(self, arguments):
        message = SimpleNamespace(reply_text=AsyncMock())
        update = SimpleNamespace(effective_message=message, effective_user=SimpleNamespace(id=100))
        await admin_command_handlers.give_key_command_handler(update, SimpleNamespace(args=arguments))
        return message

    def assert_state_and_history(self, holder_id, is_in_mailbox, history_holders):
        with database_connection(self.path) as connection:
            state = connection.execute(
                "SELECT current_holder_id, owner_member_id, is_in_mailbox FROM keys WHERE id = 1"
            ).fetchone()
            history = connection.execute(
                "SELECT holder_id FROM key_holder_history WHERE key_id = 1 ORDER BY event_id"
            ).fetchall()
        self.assertEqual((holder_id, 1, int(is_in_mailbox)), state)
        self.assertEqual([(holder,) for holder in history_holders], history)

    def assert_start_menu(self, message, holder_actions):
        markup = message.edit_text.await_args.kwargs["reply_markup"]
        callbacks = {button.callback_data for row in markup.inline_keyboard for button in row}
        self.assertEqual(holder_actions, HOLDER_KEY_HANDOVER_CALLBACK in callbacks)
        self.assertEqual(holder_actions, HOLDER_KEY_RETURN_MAILBOX_CALLBACK in callbacks)
        self.assertEqual(not holder_actions, RECEIVER_MAILBOX_KEY_OBTAINED_CALLBACK in callbacks)

    async def test_return_prompts_and_cancellation_do_not_write_state_or_history(self):
        message = await self.press(200, HOLDER_KEY_RETURN_MAILBOX_CALLBACK)
        self.assertEqual(
            "Return key 1 (Red) to the mailbox for room 101.", message.edit_text.await_args.args[0]
        )
        self.assert_state_and_history(2, False, [])
        await self.press(200, mailbox_key_return_choice_callback(1), message)
        self.assert_state_and_history(2, False, [])
        await self.press(200, HOLDER_KEY_RETURN_MAILBOX_CANCEL_CALLBACK, message)
        self.assertEqual(messages.HOLDER_CHANGE_CANCELLED_TEXT, message.edit_text.await_args.args[0])
        self.assert_state_and_history(2, False, [])
        self.assert_start_menu(message, True)

    async def test_return_and_pickup_record_destination_and_refresh_menus(self):
        returned = await self.press(200, mailbox_key_return_confirm_callback(1))
        self.assert_state_and_history(1, True, [1])
        self.assertEqual(
            messages.MAILBOX_HOLDER_RETURNED_TEXT.format(key_id="1 (Red)"),
            returned.edit_text.await_args.args[0],
        )
        self.assert_start_menu(returned, False)
        owner_menu = await self.press(100, GET_STARTING_MESSAGE_CALLBACK)
        self.assert_start_menu(owner_menu, False)

        receiver = await self.press(300, mailbox_key_choice_callback(1))
        self.assert_state_and_history(1, True, [1])
        await self.press(300, mailbox_key_obtained_confirm_callback(1), receiver)
        self.assert_state_and_history(3, False, [1, 3])
        self.assertEqual(
            messages.MAILBOX_RECEIVER_TAKEN_TEXT.format(key_id="1 (Red)"),
            receiver.edit_text.await_args.args[0],
        )
        self.assert_start_menu(receiver, True)

    async def test_stale_return_and_duplicate_pickup_cannot_override_state(self):
        await self.press(200, HOLDER_KEY_RETURN_MAILBOX_CALLBACK)
        await self.give_key(["1", "300", "--mailbox", "True"])
        stale_return = await self.press(200, mailbox_key_return_confirm_callback(1))
        self.assertIn("not its recorded holder", stale_return.edit_text.await_args.args[0])
        self.assert_state_and_history(3, True, [3])

        await self.press(300, mailbox_key_obtained_confirm_callback(1))
        duplicate = await self.press(200, mailbox_key_obtained_confirm_callback(1))
        self.assertEqual(
            messages.MAILBOX_RECEIVER_EMPTY_TEXT.format(key_id="1 (Red)"),
            duplicate.edit_text.await_args.args[0],
        )
        self.assert_state_and_history(3, False, [3, 3])

    async def test_pickup_cancellation_leaves_key_in_non_owners_mailbox(self):
        await self.give_key(["1", "200", "-m", "True"])
        message = await self.press(300, mailbox_key_choice_callback(1))
        await self.press(300, RECEIVER_MAILBOX_KEY_OBTAINED_CANCEL_CALLBACK, message)
        self.assertEqual(messages.MAILBOX_RECEIVER_CANCELLED_TEXT, message.edit_text.await_args.args[0])
        self.assert_state_and_history(2, True, [2])
        self.assert_start_menu(message, False)

    async def test_owner_must_confirm_pickup_before_handover_is_available(self):
        await self.give_key(["1", "100", "-m", "True"])
        blocked = await self.press(100, HOLDER_KEY_HANDOVER_CALLBACK)
        self.assertEqual(messages.HANDOVER_HOLDER_BLOCKED_TEXT, blocked.edit_text.await_args.args[0])
        self.assertIsNone(handover_flow.get_pending_handover(1))
        self.assert_state_and_history(1, True, [1])

        picked_up = await self.press(100, mailbox_key_obtained_confirm_callback(1))
        self.assert_state_and_history(1, False, [1, 1])
        self.assert_start_menu(picked_up, True)
        await self.press(100, HOLDER_KEY_HANDOVER_CALLBACK)
        self.assertIsNotNone(handover_flow.get_pending_handover(1))
        self.assert_state_and_history(1, False, [1, 1])

    async def test_completed_handover_records_receiver_in_hands(self):
        holder_message = await self.press(200, HOLDER_KEY_HANDOVER_CALLBACK)
        pending = handover_flow.get_pending_handover(1)
        self.assertIsNotNone(pending)
        self.assert_state_and_history(2, False, [])
        receiver_message = await self.press(300, handover_key_choice_callback(1))
        self.assert_state_and_history(2, False, [])
        await self.press(300, handover_key_obtained_confirm_callback(1), receiver_message)
        self.assert_state_and_history(3, False, [3])
        self.assertIsNone(handover_flow.get_pending_handover(1))
        await asyncio.sleep(0)
        self.assertTrue(pending.timeout_task.cancelled())
        self.assert_start_menu(holder_message, False)
        self.assert_start_menu(receiver_message, True)
        self.assertEqual(
            "Recorded: Cara Receiver received key 1 (Red) from Ben Borrower.",
            receiver_message.edit_text.await_args.args[0],
        )

    async def test_handover_cancellation_preserves_possession_and_history(self):
        message = await self.press(200, HOLDER_KEY_HANDOVER_CALLBACK)
        pending = handover_flow.get_pending_handover(1)
        await self.press(200, HOLDER_KEY_HANDOVER_CANCEL_CALLBACK, message)
        self.assert_state_and_history(2, False, [])
        self.assertIsNone(handover_flow.get_pending_handover(1))
        await asyncio.sleep(0)
        self.assertTrue(pending.timeout_task.cancelled())
        self.assert_start_menu(message, True)

    async def test_handover_expiration_preserves_possession_and_history(self):
        with patch.object(handover_flow, "HANDOVER_WINDOW_SECONDS", 0):
            message = await self.press(200, HOLDER_KEY_HANDOVER_CALLBACK)
            pending = handover_flow.get_pending_handover(1)
            await pending.timeout_task
        self.assert_state_and_history(2, False, [])
        self.assertIsNone(handover_flow.get_pending_handover(1))
        self.assertEqual(messages.HANDOVER_HOLDER_EXPIRED_TEXT, message.edit_text.await_args.args[0])
        self.assert_start_menu(message, True)

    async def test_admin_assignment_cancels_pending_handover_and_blocks_old_confirmation(self):
        await self.press(200, HOLDER_KEY_HANDOVER_CALLBACK)
        pending = handover_flow.get_pending_handover(1)
        await self.give_key(["1", "300", "--mailbox", "True"])
        self.assert_state_and_history(3, True, [3])
        self.assertIsNone(handover_flow.get_pending_handover(1))
        await asyncio.sleep(0)
        self.assertTrue(pending.timeout_task.cancelled())

        old_confirmation = await self.press(300, handover_key_obtained_confirm_callback(1))
        self.assertEqual(
            messages.HANDOVER_RECEIVER_MISSING_TEXT.format(key_id="1 (Red)"),
            old_confirmation.edit_text.await_args.args[0],
        )
        self.assert_state_and_history(3, True, [3])

    async def test_rejected_admin_assignment_does_not_cancel_pending_handover(self):
        await self.press(200, HOLDER_KEY_HANDOVER_CALLBACK)
        pending = handover_flow.get_pending_handover(1)
        for arguments in (
            ["1", "999", "--mailbox", "True"],
            ["999", "300", "--mailbox", "True"],
            ["1", "300", "--mailbox", "invalid"],
        ):
            with self.subTest(arguments=arguments):
                await self.give_key(arguments)
                self.assert_state_and_history(2, False, [])
                self.assertIs(pending, handover_flow.get_pending_handover(1))
                self.assertFalse(pending.timeout_task.cancelled())

    async def test_menu_ignores_mailbox_keys_and_inactive_keys(self):
        change_key_holder(self.path, 1, 2, is_in_mailbox=True)
        with database_connection(self.path) as connection:
            connection.execute(
                """INSERT INTO keys (id, current_holder_id, owner_member_id, is_active)
                   VALUES (2, 2, 1, 0)"""
            )
        menu = await self.press(200, GET_STARTING_MESSAGE_CALLBACK)
        self.assert_start_menu(menu, False)
        set_key_active(self.path, 2, True)
        menu = await self.press(200, GET_STARTING_MESSAGE_CALLBACK)
        self.assert_start_menu(menu, True)

    async def test_info_and_status_show_non_owner_mailbox_and_subsequent_pickup(self):
        await self.give_key(["1", "200", "-m", "True"])
        info = await self.press(300, RECEIVER_KEY_INFO_CALLBACK)
        text = info.edit_text.await_args.args[0]
        for expected in ("Ben Borrower", "mailbox", "room 202", "Telegram name: @ben"):
            self.assertIn(expected, text)
        await self.press(300, mailbox_key_obtained_confirm_callback(1))
        info = await self.press(200, RECEIVER_KEY_INFO_CALLBACK)
        self.assertIn("currently held by Cara Receiver, room 303", info.edit_text.await_args.args[0])

        message = SimpleNamespace(reply_text=AsyncMock())
        update = SimpleNamespace(effective_message=message, effective_user=SimpleNamespace(id=100))
        await admin_command_handlers.key_status_command_handler(update, SimpleNamespace(args=["1"]))
        text = message.reply_text.await_args.args[0]
        for expected in ("Key: 1 (Red)", "Location: member's hands", "Name: Cara Receiver", "Name: Ada Owner"):
            self.assertIn(expected, text)
