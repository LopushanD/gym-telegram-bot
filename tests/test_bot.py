import asyncio
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import src.bot as bot
from src.database import initialize_database
from src.key_service import ConfirmKeyResult, ConfirmKeyStatus, HandoverResult, HandoverStatus
from src import messages


def create_callback_update(
    callback_data,
    telegram_user_id=None,
    full_name=None,
    username=None,
    chat_id=None,
):
    message = SimpleNamespace(
        reply_text=AsyncMock(),
        delete=AsyncMock(),
        chat_id=chat_id,
    )
    from_user = None
    if telegram_user_id is not None:
        from_user = SimpleNamespace(
            id=telegram_user_id,
            full_name=full_name,
            username=username,
        )

    query = SimpleNamespace(
        data=callback_data,
        message=message,
        answer=AsyncMock(),
        from_user=from_user,
    )
    return SimpleNamespace(callback_query=query)


def assert_reply_text_with_start_keyboard(
    test_case,
    reply_text_mock,
    expected_text,
    includes_holder_actions=False,
):
    reply_text_mock.assert_awaited_once()
    args, kwargs = reply_text_mock.call_args
    keyboard = kwargs["reply_markup"].inline_keyboard

    test_case.assertEqual((expected_text,), args)
    if includes_holder_actions:
        test_case.assertEqual("Hand over the key", keyboard[0][0].text)
        test_case.assertEqual(bot.KEY_HANDOVER_CALLBACK, keyboard[0][0].callback_data)
        test_case.assertEqual(1, len(keyboard))
        return

    test_case.assertEqual("Request the key", keyboard[0][0].text)
    test_case.assertEqual(bot.KEY_REQUEST_CALLBACK, keyboard[0][0].callback_data)
    test_case.assertEqual("Got the key", keyboard[1][0].text)
    test_case.assertEqual(bot.KEY_OBTAINED_CALLBACK, keyboard[1][0].callback_data)
    test_case.assertEqual(2, len(keyboard))


def assert_last_reply_text_with_start_keyboard(
    test_case,
    reply_text_mock,
    expected_text,
    includes_holder_actions=False,
):
    args, kwargs = reply_text_mock.await_args_list[-1]
    keyboard = kwargs["reply_markup"].inline_keyboard

    test_case.assertEqual((expected_text,), args)
    if includes_holder_actions:
        test_case.assertEqual("Hand over the key", keyboard[0][0].text)
        test_case.assertEqual(bot.KEY_HANDOVER_CALLBACK, keyboard[0][0].callback_data)
        test_case.assertEqual(1, len(keyboard))
        return

    test_case.assertEqual("Request the key", keyboard[0][0].text)
    test_case.assertEqual(bot.KEY_REQUEST_CALLBACK, keyboard[0][0].callback_data)
    test_case.assertEqual("Got the key", keyboard[1][0].text)
    test_case.assertEqual(bot.KEY_OBTAINED_CALLBACK, keyboard[1][0].callback_data)
    test_case.assertEqual(2, len(keyboard))


def assert_keyboard_does_not_include_callback(test_case, reply_text_mock, callback_data):
    _, kwargs = reply_text_mock.call_args
    keyboard = kwargs["reply_markup"].inline_keyboard
    callback_data_values = [
        button.callback_data
        for row in keyboard
        for button in row
    ]

    test_case.assertNotIn(callback_data, callback_data_values)


class BotHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self):
        for pending_handover in bot.PENDING_HANDOVERS.values():
            pending_handover.timeout_task.cancel()
        bot.PENDING_HANDOVERS.clear()

    async def test_reply_with_start_state_sends_main_keyboard(self):
        message = SimpleNamespace(reply_text=AsyncMock())

        await bot.reply_with_start_state(message)

        assert_reply_text_with_start_keyboard(
            self,
            message.reply_text,
            messages.START_STATE_TEXT,
        )

    async def test_reply_with_start_state_adds_holder_action_for_current_holder(self):
        message = SimpleNamespace(reply_text=AsyncMock())

        with patch.object(
            bot,
            "user_currently_holds_key",
            return_value=True,
        ) as user_currently_holds_key:
            await bot.reply_with_start_state(
                message,
                telegram_user_id=123,
            )

        user_currently_holds_key.assert_called_once_with(
            bot.DEFAULT_DATABASE_PATH,
            123,
            bot.DEFAULT_KEY_ID,
        )
        assert_reply_text_with_start_keyboard(
            self,
            message.reply_text,
            messages.START_STATE_TEXT,
            includes_holder_actions=True,
        )
        assert_keyboard_does_not_include_callback(
            self,
            message.reply_text,
            bot.KEY_OBTAINED_CALLBACK,
        )

    async def test_reply_with_start_state_keeps_default_buttons_for_non_holder(self):
        message = SimpleNamespace(reply_text=AsyncMock())

        with patch.object(
            bot,
            "user_currently_holds_key",
            return_value=False,
        ):
            await bot.reply_with_start_state(
                message,
                telegram_user_id=456,
            )

        assert_reply_text_with_start_keyboard(
            self,
            message.reply_text,
            messages.START_STATE_TEXT,
        )

    async def test_start_command_returns_to_start_state(self):
        update = SimpleNamespace(
            effective_user=SimpleNamespace(id=123),
            message=SimpleNamespace(reply_text=AsyncMock()),
        )

        with patch.object(
            bot,
            "user_currently_holds_key",
            return_value=True,
        ):
            await bot.start_state_command_handler(update, SimpleNamespace())

        assert_reply_text_with_start_keyboard(
            self,
            update.message.reply_text,
            messages.START_STATE_TEXT,
            includes_holder_actions=True,
        )
        assert_keyboard_does_not_include_callback(
            self,
            update.message.reply_text,
            bot.KEY_OBTAINED_CALLBACK,
        )

    async def test_request_key_callback_replies_with_current_holder(self):
        update = create_callback_update(bot.KEY_REQUEST_CALLBACK)

        with patch.object(
            bot,
            "get_key_holder",
            return_value=SimpleNamespace(name="Dima", surname="Ivanov", room_number=1234),
        ):
            await bot.callback_query_handler(update, SimpleNamespace())

        update.callback_query.answer.assert_awaited_once_with("Looking up the key holder...")
        update.callback_query.message.delete.assert_awaited_once_with()
        assert_reply_text_with_start_keyboard(
            self,
            update.callback_query.message.reply_text,
            "The key is currently held by Dima Ivanov, room 1234.",
        )

    async def test_request_key_callback_replies_when_key_is_missing(self):
        update = create_callback_update(bot.KEY_REQUEST_CALLBACK)

        with patch.object(bot, "get_key_holder", return_value=None):
            await bot.callback_query_handler(update, SimpleNamespace())

        update.callback_query.answer.assert_awaited_once_with("Looking up the key holder...")
        update.callback_query.message.delete.assert_awaited_once_with()
        assert_reply_text_with_start_keyboard(
            self,
            update.callback_query.message.reply_text,
            "No key is registered in the database yet.",
        )

    async def test_got_key_callback_asks_for_confirmation(self):
        update = create_callback_update(bot.KEY_OBTAINED_CALLBACK)

        await bot.callback_query_handler(update, SimpleNamespace())

        update.callback_query.answer.assert_awaited_once_with("Please confirm.")
        update.callback_query.message.delete.assert_awaited_once_with()
        update.callback_query.message.reply_text.assert_awaited_once()
        args, kwargs = update.callback_query.message.reply_text.call_args
        keyboard = kwargs["reply_markup"].inline_keyboard

        self.assertEqual(("Please confirm that you got the key.",), args)
        self.assertEqual("Confirm", keyboard[0][0].text)
        self.assertEqual(bot.CONFIRM_KEY_OBTAINED_CALLBACK, keyboard[0][0].callback_data)
        self.assertEqual("Cancel", keyboard[0][1].text)
        self.assertEqual(bot.CANCEL_KEY_OBTAINED_CALLBACK, keyboard[0][1].callback_data)

    async def test_key_handover_callback_gives_current_holder_instructions(self):
        update = create_callback_update(
            bot.KEY_HANDOVER_CALLBACK,
            telegram_user_id=123,
            full_name="Member One",
        )

        with (
            patch.object(
                bot,
                "start_key_handover",
                return_value=HandoverResult(status=HandoverStatus.READY),
            ),
            patch.object(bot, "user_currently_holds_key", return_value=True),
        ):
            await bot.callback_query_handler(update, SimpleNamespace())

        update.callback_query.answer.assert_awaited_once_with("Ready for handover.")
        update.callback_query.message.delete.assert_awaited_once_with()
        assert_reply_text_with_start_keyboard(
            self,
            update.callback_query.message.reply_text,
            "Give the key to the next member and ask them to press Got the key.",
            includes_holder_actions=True,
        )
        assert_keyboard_does_not_include_callback(
            self,
            update.callback_query.message.reply_text,
            bot.KEY_OBTAINED_CALLBACK,
        )
        self.assertIn(bot.DEFAULT_KEY_ID, bot.PENDING_HANDOVERS)
        self.assertEqual(
            123,
            bot.PENDING_HANDOVERS[bot.DEFAULT_KEY_ID].holder_user_id,
        )

    async def test_got_key_during_pending_handover_asks_member_to_confirm(self):
        handover_update = create_callback_update(
            bot.KEY_HANDOVER_CALLBACK,
            telegram_user_id=123,
            full_name="Member One",
        )
        obtained_update = create_callback_update(
            bot.KEY_OBTAINED_CALLBACK,
            telegram_user_id=456,
            full_name="Member Two",
        )

        with (
            patch.object(
                bot,
                "start_key_handover",
                return_value=HandoverResult(status=HandoverStatus.READY),
            ),
            patch.object(
                bot,
                "user_currently_holds_key",
                side_effect=lambda database_path, telegram_user_id, key_id: (
                    telegram_user_id == 123
                ),
            ),
            patch.object(bot, "confirm_key_obtained") as confirm_key_obtained,
        ):
            await bot.callback_query_handler(handover_update, SimpleNamespace())
            await bot.callback_query_handler(obtained_update, SimpleNamespace())

        confirm_key_obtained.assert_not_called()
        obtained_update.callback_query.answer.assert_awaited_once_with(
            "Please confirm."
        )
        obtained_update.callback_query.message.reply_text.assert_awaited_once()
        args, kwargs = obtained_update.callback_query.message.reply_text.call_args
        keyboard = kwargs["reply_markup"].inline_keyboard

        self.assertEqual(
            ("Please confirm that you got the key from Member One.",),
            args,
        )
        self.assertEqual("Confirm", keyboard[0][0].text)
        self.assertEqual(bot.CONFIRM_KEY_OBTAINED_CALLBACK, keyboard[0][0].callback_data)
        self.assertEqual("Cancel", keyboard[0][1].text)
        self.assertEqual(bot.CANCEL_KEY_OBTAINED_CALLBACK, keyboard[0][1].callback_data)
        self.assertIn(bot.DEFAULT_KEY_ID, bot.PENDING_HANDOVERS)

    async def test_confirm_completes_pending_handover_without_database_update(self):
        handover_update = create_callback_update(
            bot.KEY_HANDOVER_CALLBACK,
            telegram_user_id=123,
            full_name="Member One",
        )
        confirm_update = create_callback_update(
            bot.CONFIRM_KEY_OBTAINED_CALLBACK,
            telegram_user_id=456,
            full_name="Member Two",
        )

        with (
            patch.object(
                bot,
                "start_key_handover",
                return_value=HandoverResult(status=HandoverStatus.READY),
            ),
            patch.object(
                bot,
                "user_currently_holds_key",
                side_effect=lambda database_path, telegram_user_id, key_id: (
                    telegram_user_id == 123
                ),
            ),
            patch.object(bot, "confirm_key_obtained") as confirm_key_obtained,
        ):
            await bot.callback_query_handler(handover_update, SimpleNamespace())
            await bot.callback_query_handler(confirm_update, SimpleNamespace())

        confirm_key_obtained.assert_not_called()
        confirm_update.callback_query.answer.assert_awaited_once_with(
            "Handover completed."
        )
        self.assertEqual(
            2,
            handover_update.callback_query.message.reply_text.await_count,
        )
        assert_last_reply_text_with_start_keyboard(
            self,
            handover_update.callback_query.message.reply_text,
            "The key was handed over from Member One to Member Two.",
            includes_holder_actions=True,
        )
        assert_reply_text_with_start_keyboard(
            self,
            confirm_update.callback_query.message.reply_text,
            "The key was handed over from Member One to Member Two.",
        )
        self.assertNotIn(bot.DEFAULT_KEY_ID, bot.PENDING_HANDOVERS)

    async def test_completed_handover_sends_one_message_in_shared_chat(self):
        handover_update = create_callback_update(
            bot.KEY_HANDOVER_CALLBACK,
            telegram_user_id=123,
            full_name="Member One",
            chat_id=10,
        )
        obtained_update = create_callback_update(
            bot.CONFIRM_KEY_OBTAINED_CALLBACK,
            telegram_user_id=456,
            full_name="Member Two",
            chat_id=10,
        )

        with (
            patch.object(
                bot,
                "start_key_handover",
                return_value=HandoverResult(status=HandoverStatus.READY),
            ),
            patch.object(
                bot,
                "user_currently_holds_key",
                side_effect=lambda database_path, telegram_user_id, key_id: (
                    telegram_user_id == 123
                ),
            ),
        ):
            await bot.callback_query_handler(handover_update, SimpleNamespace())
            await bot.callback_query_handler(obtained_update, SimpleNamespace())

        self.assertEqual(
            2,
            handover_update.callback_query.message.reply_text.await_count,
        )
        obtained_update.callback_query.message.reply_text.assert_not_awaited()
        assert_last_reply_text_with_start_keyboard(
            self,
            handover_update.callback_query.message.reply_text,
            "The key was handed over from Member One to Member Two.",
            includes_holder_actions=True,
        )

    async def test_pending_handover_times_out_and_keeps_current_holder(self):
        update = create_callback_update(
            bot.KEY_HANDOVER_CALLBACK,
            telegram_user_id=123,
            full_name="Member One",
        )

        with (
            patch.object(bot, "HANDOVER_WINDOW_SECONDS", 0),
            patch.object(
                bot,
                "start_key_handover",
                return_value=HandoverResult(status=HandoverStatus.READY),
            ),
            patch.object(bot, "user_currently_holds_key", return_value=True),
        ):
            await bot.callback_query_handler(update, SimpleNamespace())
            await asyncio.sleep(0)
            await asyncio.sleep(0)

        self.assertEqual(2, update.callback_query.message.reply_text.await_count)
        assert_last_reply_text_with_start_keyboard(
            self,
            update.callback_query.message.reply_text,
            "The handover procedure failed. You remain the recorded key holder.",
            includes_holder_actions=True,
        )
        self.assertNotIn(bot.DEFAULT_KEY_ID, bot.PENDING_HANDOVERS)

    async def test_cancel_pending_handover_returns_both_members_to_start_state(self):
        handover_update = create_callback_update(
            bot.KEY_HANDOVER_CALLBACK,
            telegram_user_id=123,
            full_name="Member One",
        )
        cancel_update = create_callback_update(
            bot.CANCEL_KEY_OBTAINED_CALLBACK,
            telegram_user_id=456,
            full_name="Member Two",
        )

        with (
            patch.object(
                bot,
                "start_key_handover",
                return_value=HandoverResult(status=HandoverStatus.READY),
            ),
            patch.object(
                bot,
                "user_currently_holds_key",
                side_effect=lambda database_path, telegram_user_id, key_id: (
                    telegram_user_id == 123
                ),
            ),
        ):
            await bot.callback_query_handler(handover_update, SimpleNamespace())
            await bot.callback_query_handler(cancel_update, SimpleNamespace())

        cancel_update.callback_query.answer.assert_awaited_once_with("Cancelled.")
        assert_last_reply_text_with_start_keyboard(
            self,
            handover_update.callback_query.message.reply_text,
            "The handover procedure failed. You remain the recorded key holder.",
            includes_holder_actions=True,
        )
        assert_reply_text_with_start_keyboard(
            self,
            cancel_update.callback_query.message.reply_text,
            "Cancelled. No key-obtained action was recorded.",
        )
        self.assertNotIn(bot.DEFAULT_KEY_ID, bot.PENDING_HANDOVERS)

    async def test_current_holder_cannot_complete_own_pending_handover(self):
        handover_update = create_callback_update(
            bot.KEY_HANDOVER_CALLBACK,
            telegram_user_id=123,
            full_name="Member One",
        )
        obtained_update = create_callback_update(
            bot.KEY_OBTAINED_CALLBACK,
            telegram_user_id=123,
            full_name="Member One",
        )

        with (
            patch.object(
                bot,
                "start_key_handover",
                return_value=HandoverResult(status=HandoverStatus.READY),
            ),
            patch.object(bot, "user_currently_holds_key", return_value=True),
        ):
            await bot.callback_query_handler(handover_update, SimpleNamespace())
            await bot.callback_query_handler(obtained_update, SimpleNamespace())

        obtained_update.callback_query.answer.assert_awaited_once_with(
            "Ask the next member to press Got the key."
        )
        assert_reply_text_with_start_keyboard(
            self,
            obtained_update.callback_query.message.reply_text,
            "The current holder cannot complete their own handover.",
            includes_holder_actions=True,
        )
        self.assertIn(bot.DEFAULT_KEY_ID, bot.PENDING_HANDOVERS)

    async def test_key_handover_callback_rejects_non_holder(self):
        update = create_callback_update(bot.KEY_HANDOVER_CALLBACK, telegram_user_id=456)

        with (
            patch.object(
                bot,
                "start_key_handover",
                return_value=HandoverResult(status=HandoverStatus.NOT_CURRENT_HOLDER),
            ),
            patch.object(bot, "user_currently_holds_key", return_value=False),
        ):
            await bot.callback_query_handler(update, SimpleNamespace())

        update.callback_query.answer.assert_awaited_once_with(
            "Only the current holder can hand over the key."
        )
        update.callback_query.message.delete.assert_awaited_once_with()
        assert_reply_text_with_start_keyboard(
            self,
            update.callback_query.message.reply_text,
            "Only the current key holder can start a handover.",
        )

    async def test_confirm_key_obtained_callback_updates_holder_and_history(self):
        update = create_callback_update(
            bot.CONFIRM_KEY_OBTAINED_CALLBACK,
            telegram_user_id=123,
        )

        with (
            patch.object(
                bot,
                "confirm_key_obtained",
                return_value=ConfirmKeyResult(status=ConfirmKeyStatus.CONFIRMED),
            ) as confirm_key_obtained,
            patch.object(
                bot,
                "user_currently_holds_key",
                return_value=True,
            ),
        ):
            await bot.callback_query_handler(update, SimpleNamespace())

        confirm_key_obtained.assert_called_once_with(
            bot.DEFAULT_DATABASE_PATH,
            123,
            bot.DEFAULT_KEY_ID,
        )

        update.callback_query.answer.assert_awaited_once_with("Confirmed.")
        update.callback_query.message.delete.assert_awaited_once_with()
        assert_reply_text_with_start_keyboard(
            self,
            update.callback_query.message.reply_text,
            "Confirmed. You are now recorded as the key holder.",
            includes_holder_actions=True,
        )
        assert_keyboard_does_not_include_callback(
            self,
            update.callback_query.message.reply_text,
            bot.KEY_OBTAINED_CALLBACK,
        )

    async def test_confirm_key_obtained_callback_updates_database(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            initialize_database(database_path)
            with sqlite3.connect(database_path) as connection:
                first_holder_id = connection.execute(
                    """
                    INSERT INTO gym_members (
                        telegram_user_id,
                        name,
                        surname,
                        room_number
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (111, "Dima", "Ivanov", 1234),
                ).lastrowid
                new_holder_id = connection.execute(
                    """
                    INSERT INTO gym_members (
                        telegram_user_id,
                        name,
                        surname,
                        room_number
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (222, "Alex", "Petrov", 4321),
                ).lastrowid
                key_id = connection.execute(
                    """
                    INSERT INTO keys (current_holder_id)
                    VALUES (?)
                    """,
                    (first_holder_id,),
                ).lastrowid

            update = create_callback_update(
                bot.CONFIRM_KEY_OBTAINED_CALLBACK,
                telegram_user_id=222,
            )

            with patch.object(bot, "DEFAULT_DATABASE_PATH", database_path):
                await bot.callback_query_handler(update, SimpleNamespace())

            with sqlite3.connect(database_path) as connection:
                current_holder_id = connection.execute(
                    "SELECT current_holder_id FROM keys WHERE id = ?",
                    (key_id,),
                ).fetchone()
                history_record = connection.execute(
                    """
                    SELECT key_id, holder_id
                    FROM key_holder_history
                    WHERE key_id = ?
                    """,
                    (key_id,),
                ).fetchone()

            self.assertEqual((new_holder_id,), current_holder_id)
            self.assertEqual((key_id, new_holder_id), history_record)
            assert_reply_text_with_start_keyboard(
                self,
                update.callback_query.message.reply_text,
                "Confirmed. You are now recorded as the key holder.",
                includes_holder_actions=True,
            )
            assert_keyboard_does_not_include_callback(
                self,
                update.callback_query.message.reply_text,
                bot.KEY_OBTAINED_CALLBACK,
            )

    async def test_confirm_key_obtained_callback_rejects_missing_telegram_user(self):
        update = create_callback_update(bot.CONFIRM_KEY_OBTAINED_CALLBACK)

        with patch.object(
            bot,
            "confirm_key_obtained",
            return_value=ConfirmKeyResult(
                status=ConfirmKeyStatus.MISSING_TELEGRAM_USER,
            ),
        ) as confirm_key_obtained:
            await bot.callback_query_handler(update, SimpleNamespace())

        confirm_key_obtained.assert_called_once_with(
            bot.DEFAULT_DATABASE_PATH,
            None,
            bot.DEFAULT_KEY_ID,
        )
        update.callback_query.answer.assert_awaited_once_with("Could not identify you.")
        update.callback_query.message.delete.assert_awaited_once_with()
        assert_reply_text_with_start_keyboard(
            self,
            update.callback_query.message.reply_text,
            "Could not confirm key ownership because Telegram user is missing.",
        )

    async def test_confirm_key_obtained_callback_rejects_unregistered_user(self):
        update = create_callback_update(
            bot.CONFIRM_KEY_OBTAINED_CALLBACK,
            telegram_user_id=123,
        )

        with (
            patch.object(
                bot,
                "confirm_key_obtained",
                return_value=ConfirmKeyResult(
                    status=ConfirmKeyStatus.USER_NOT_REGISTERED,
                ),
            ) as confirm_key_obtained,
            patch.object(bot, "user_currently_holds_key", return_value=False),
        ):
            await bot.callback_query_handler(update, SimpleNamespace())

        confirm_key_obtained.assert_called_once_with(
            bot.DEFAULT_DATABASE_PATH,
            123,
            bot.DEFAULT_KEY_ID,
        )
        update.callback_query.answer.assert_awaited_once_with("You are not registered.")
        update.callback_query.message.delete.assert_awaited_once_with()
        assert_reply_text_with_start_keyboard(
            self,
            update.callback_query.message.reply_text,
            "Could not confirm key ownership because you are not registered.",
        )

    async def test_cancel_key_obtained_callback_replies_with_cancellation(self):
        update = create_callback_update(bot.CANCEL_KEY_OBTAINED_CALLBACK)

        await bot.callback_query_handler(update, SimpleNamespace())

        update.callback_query.answer.assert_awaited_once_with("Cancelled.")
        update.callback_query.message.delete.assert_awaited_once_with()
        assert_reply_text_with_start_keyboard(
            self,
            update.callback_query.message.reply_text,
            "Cancelled. No key-obtained action was recorded.",
        )

    async def test_unknown_callback_returns_to_start_state(self):
        update = create_callback_update("unknown")

        await bot.callback_query_handler(update, SimpleNamespace())

        update.callback_query.answer.assert_awaited_once_with("Unknown button.")
        update.callback_query.message.delete.assert_awaited_once_with()
        assert_reply_text_with_start_keyboard(
            self,
            update.callback_query.message.reply_text,
            "Unknown button. Back to the start.",
        )

    async def test_callback_start_state_includes_holder_action_for_current_holder(self):
        update = create_callback_update("unknown", telegram_user_id=123)

        with patch.object(
            bot,
            "user_currently_holds_key",
            return_value=True,
        ):
            await bot.callback_query_handler(update, SimpleNamespace())

        assert_reply_text_with_start_keyboard(
            self,
            update.callback_query.message.reply_text,
            "Unknown button. Back to the start.",
            includes_holder_actions=True,
        )
        assert_keyboard_does_not_include_callback(
            self,
            update.callback_query.message.reply_text,
            bot.KEY_OBTAINED_CALLBACK,
        )


if __name__ == "__main__":
    unittest.main()
