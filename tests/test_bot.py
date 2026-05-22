import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import testBot


def create_callback_update(callback_data):
    message = SimpleNamespace(reply_text=AsyncMock(), delete=AsyncMock())
    query = SimpleNamespace(
        data=callback_data,
        message=message,
        answer=AsyncMock(),
    )
    return SimpleNamespace(callback_query=query)


def assert_reply_text_with_start_keyboard(test_case, reply_text_mock, expected_text):
    reply_text_mock.assert_awaited_once()
    args, kwargs = reply_text_mock.call_args
    keyboard = kwargs["reply_markup"].inline_keyboard

    test_case.assertEqual((expected_text,), args)
    test_case.assertEqual("Request the key", keyboard[0][0].text)
    test_case.assertEqual(testBot.KEY_REQUEST_CALLBACK, keyboard[0][0].callback_data)
    test_case.assertEqual("Got the key", keyboard[1][0].text)
    test_case.assertEqual(testBot.KEY_OBTAINED_CALLBACK, keyboard[1][0].callback_data)


class BotHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_sends_main_keyboard(self):
        update = SimpleNamespace(message=SimpleNamespace(reply_text=AsyncMock()))

        await testBot.start(update, SimpleNamespace())

        update.message.reply_text.assert_awaited_once()
        _, kwargs = update.message.reply_text.call_args
        keyboard = kwargs["reply_markup"].inline_keyboard

        self.assertEqual("Request the key", keyboard[0][0].text)
        self.assertEqual(testBot.KEY_REQUEST_CALLBACK, keyboard[0][0].callback_data)
        self.assertEqual("Got the key", keyboard[1][0].text)
        self.assertEqual(testBot.KEY_OBTAINED_CALLBACK, keyboard[1][0].callback_data)

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

    async def test_confirm_key_obtained_callback_replies_with_confirmation(self):
        update = create_callback_update(testBot.CONFIRM_KEY_OBTAINED_CALLBACK)

        await testBot.request_key_handler(update, SimpleNamespace())

        update.callback_query.answer.assert_awaited_once_with("Confirmed.")
        update.callback_query.message.delete.assert_awaited_once_with()
        assert_reply_text_with_start_keyboard(
            self,
            update.callback_query.message.reply_text,
            "Confirmed. The key-obtained action is working.",
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


if __name__ == "__main__":
    unittest.main()
