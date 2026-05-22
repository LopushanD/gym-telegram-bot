import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import testBot
from database import initialize_database


def create_callback_update(callback_data, telegram_user_id=None):
    message = SimpleNamespace(reply_text=AsyncMock(), delete=AsyncMock())
    query = SimpleNamespace(
        data=callback_data,
        message=message,
        answer=AsyncMock(),
        from_user=(
            SimpleNamespace(id=telegram_user_id)
            if telegram_user_id is not None
            else None
        ),
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
        test_case.assertEqual(testBot.KEY_HANDOVER_CALLBACK, keyboard[0][0].callback_data)
        test_case.assertEqual(1, len(keyboard))
        return

    test_case.assertEqual("Request the key", keyboard[0][0].text)
    test_case.assertEqual(testBot.KEY_REQUEST_CALLBACK, keyboard[0][0].callback_data)
    test_case.assertEqual("Got the key", keyboard[1][0].text)
    test_case.assertEqual(testBot.KEY_OBTAINED_CALLBACK, keyboard[1][0].callback_data)
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
    async def test_reply_with_start_state_sends_main_keyboard(self):
        message = SimpleNamespace(reply_text=AsyncMock())

        await testBot.reply_with_start_state(message)

        assert_reply_text_with_start_keyboard(
            self,
            message.reply_text,
            testBot.START_STATE_TEXT,
        )

    async def test_reply_with_start_state_adds_holder_action_for_current_holder(self):
        message = SimpleNamespace(reply_text=AsyncMock())

        with patch.object(
            testBot,
            "get_current_key_holder",
            return_value=("Dima", "Ivanov", 1234),
        ) as get_current_holder:
            await testBot.reply_with_start_state(
                message,
                telegram_user_id=123,
            )

        get_current_holder.assert_called_once_with(
            testBot.DEFAULT_DATABASE_PATH,
            key_id=testBot.DEFAULT_KEY_ID,
            telegram_user_id=123,
        )
        assert_reply_text_with_start_keyboard(
            self,
            message.reply_text,
            testBot.START_STATE_TEXT,
            includes_holder_actions=True,
        )
        assert_keyboard_does_not_include_callback(
            self,
            message.reply_text,
            testBot.KEY_OBTAINED_CALLBACK,
        )

    async def test_reply_with_start_state_keeps_default_buttons_for_non_holder(self):
        message = SimpleNamespace(reply_text=AsyncMock())

        with patch.object(
            testBot,
            "get_current_key_holder",
            return_value=None,
        ):
            await testBot.reply_with_start_state(
                message,
                telegram_user_id=456,
            )

        assert_reply_text_with_start_keyboard(
            self,
            message.reply_text,
            testBot.START_STATE_TEXT,
        )

    async def test_start_command_returns_to_start_state(self):
        update = SimpleNamespace(
            effective_user=SimpleNamespace(id=123),
            message=SimpleNamespace(reply_text=AsyncMock()),
        )

        with patch.object(
            testBot,
            "get_current_key_holder",
            return_value=("Dima", "Ivanov", 1234),
        ):
            await testBot.start_state_command_handler(update, SimpleNamespace())

        assert_reply_text_with_start_keyboard(
            self,
            update.message.reply_text,
            testBot.START_STATE_TEXT,
            includes_holder_actions=True,
        )
        assert_keyboard_does_not_include_callback(
            self,
            update.message.reply_text,
            testBot.KEY_OBTAINED_CALLBACK,
        )

    async def test_request_key_callback_replies_with_current_holder(self):
        update = create_callback_update(testBot.KEY_REQUEST_CALLBACK)

        with patch.object(
            testBot,
            "get_current_key_holder",
            return_value=("Dima", "Ivanov", 1234),
        ):
            await testBot.request_key_handler(update, SimpleNamespace())

        update.callback_query.answer.assert_awaited_once_with("Looking up the key holder...")
        update.callback_query.message.delete.assert_awaited_once_with()
        assert_reply_text_with_start_keyboard(
            self,
            update.callback_query.message.reply_text,
            "The key is currently held by Dima Ivanov, room 1234.",
        )

    async def test_request_key_callback_replies_when_key_is_missing(self):
        update = create_callback_update(testBot.KEY_REQUEST_CALLBACK)

        with patch.object(testBot, "get_current_key_holder", return_value=None):
            await testBot.request_key_handler(update, SimpleNamespace())

        update.callback_query.answer.assert_awaited_once_with("Looking up the key holder...")
        update.callback_query.message.delete.assert_awaited_once_with()
        assert_reply_text_with_start_keyboard(
            self,
            update.callback_query.message.reply_text,
            "No key is registered in the database yet.",
        )

    async def test_got_key_callback_asks_for_confirmation(self):
        update = create_callback_update(testBot.KEY_OBTAINED_CALLBACK)

        await testBot.request_key_handler(update, SimpleNamespace())

        update.callback_query.answer.assert_awaited_once_with("Please confirm.")
        update.callback_query.message.delete.assert_awaited_once_with()
        update.callback_query.message.reply_text.assert_awaited_once()
        args, kwargs = update.callback_query.message.reply_text.call_args
        keyboard = kwargs["reply_markup"].inline_keyboard

        self.assertEqual(("Please confirm that you got the key.",), args)
        self.assertEqual("Confirm", keyboard[0][0].text)
        self.assertEqual(testBot.CONFIRM_KEY_OBTAINED_CALLBACK, keyboard[0][0].callback_data)
        self.assertEqual("Cancel", keyboard[0][1].text)
        self.assertEqual(testBot.CANCEL_KEY_OBTAINED_CALLBACK, keyboard[0][1].callback_data)

    async def test_key_handover_callback_gives_current_holder_instructions(self):
        update = create_callback_update(testBot.KEY_HANDOVER_CALLBACK, telegram_user_id=123)

        with (
            patch.object(
                testBot,
                "get_current_key_holder",
                return_value=("Dima", "Ivanov", 1234),
            ),
            patch.object(testBot, "on_holder_change") as on_holder_change,
        ):
            await testBot.request_key_handler(update, SimpleNamespace())

        on_holder_change.assert_not_called()
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
            testBot.KEY_OBTAINED_CALLBACK,
        )

    async def test_key_handover_callback_rejects_non_holder(self):
        update = create_callback_update(testBot.KEY_HANDOVER_CALLBACK, telegram_user_id=456)

        with (
            patch.object(testBot, "get_current_key_holder", return_value=None),
            patch.object(testBot, "on_holder_change") as on_holder_change,
        ):
            await testBot.request_key_handler(update, SimpleNamespace())

        on_holder_change.assert_not_called()
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
            testBot.CONFIRM_KEY_OBTAINED_CALLBACK,
            telegram_user_id=123,
        )

        with (
            patch.object(
                testBot,
                "get_gym_member_id_by_telegram_user_id",
                return_value=42,
            ) as get_member_id,
            patch.object(testBot, "on_holder_change") as on_holder_change,
            patch.object(
                testBot,
                "get_current_key_holder",
                return_value=("Dima", "Ivanov", 1234),
            ),
        ):
            await testBot.request_key_handler(update, SimpleNamespace())

        get_member_id.assert_called_once_with(testBot.DEFAULT_DATABASE_PATH, 123)
        on_holder_change.assert_called_once_with(
            testBot.DEFAULT_DATABASE_PATH,
            testBot.DEFAULT_KEY_ID,
            42,
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
            testBot.KEY_OBTAINED_CALLBACK,
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
                testBot.CONFIRM_KEY_OBTAINED_CALLBACK,
                telegram_user_id=222,
            )

            with patch.object(testBot, "DEFAULT_DATABASE_PATH", database_path):
                await testBot.request_key_handler(update, SimpleNamespace())

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
                testBot.KEY_OBTAINED_CALLBACK,
            )

    async def test_confirm_key_obtained_callback_rejects_missing_telegram_user(self):
        update = create_callback_update(testBot.CONFIRM_KEY_OBTAINED_CALLBACK)

        with patch.object(testBot, "on_holder_change") as on_holder_change:
            await testBot.request_key_handler(update, SimpleNamespace())

        on_holder_change.assert_not_called()
        update.callback_query.answer.assert_awaited_once_with("Could not identify you.")
        update.callback_query.message.delete.assert_awaited_once_with()
        assert_reply_text_with_start_keyboard(
            self,
            update.callback_query.message.reply_text,
            "Could not confirm key ownership because Telegram user is missing.",
        )

    async def test_confirm_key_obtained_callback_rejects_unregistered_user(self):
        update = create_callback_update(
            testBot.CONFIRM_KEY_OBTAINED_CALLBACK,
            telegram_user_id=123,
        )

        with (
            patch.object(
                testBot,
                "get_gym_member_id_by_telegram_user_id",
                return_value=None,
            ) as get_member_id,
            patch.object(testBot, "on_holder_change") as on_holder_change,
            patch.object(testBot, "get_current_key_holder", return_value=None),
        ):
            await testBot.request_key_handler(update, SimpleNamespace())

        get_member_id.assert_called_once_with(testBot.DEFAULT_DATABASE_PATH, 123)
        on_holder_change.assert_not_called()
        update.callback_query.answer.assert_awaited_once_with("You are not registered.")
        update.callback_query.message.delete.assert_awaited_once_with()
        assert_reply_text_with_start_keyboard(
            self,
            update.callback_query.message.reply_text,
            "Could not confirm key ownership because you are not registered.",
        )

    async def test_cancel_key_obtained_callback_replies_with_cancellation(self):
        update = create_callback_update(testBot.CANCEL_KEY_OBTAINED_CALLBACK)

        await testBot.request_key_handler(update, SimpleNamespace())

        update.callback_query.answer.assert_awaited_once_with("Cancelled.")
        update.callback_query.message.delete.assert_awaited_once_with()
        assert_reply_text_with_start_keyboard(
            self,
            update.callback_query.message.reply_text,
            "Cancelled. No key-obtained action was recorded.",
        )

    async def test_unknown_callback_returns_to_start_state(self):
        update = create_callback_update("unknown")

        await testBot.request_key_handler(update, SimpleNamespace())

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
            testBot,
            "get_current_key_holder",
            return_value=("Dima", "Ivanov", 1234),
        ):
            await testBot.request_key_handler(update, SimpleNamespace())

        assert_reply_text_with_start_keyboard(
            self,
            update.callback_query.message.reply_text,
            "Unknown button. Back to the start.",
            includes_holder_actions=True,
        )
        assert_keyboard_does_not_include_callback(
            self,
            update.callback_query.message.reply_text,
            testBot.KEY_OBTAINED_CALLBACK,
        )


if __name__ == "__main__":
    unittest.main()
