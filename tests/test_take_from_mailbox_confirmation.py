import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src import bot, messages
from src.key_service import TakeFromMailboxResult, TakeFromMailboxStatus
from src.keyboards import (
    RECEIVER_MAILBOX_KEY_OBTAINED_CANCEL_CALLBACK,
    RECEIVER_MAILBOX_KEY_OBTAINED_CONFIRM_CALLBACK,
    build_key_obtained_mailbox_confirmation_keyboard,
)


class TakeFromMailboxConfirmationTests(unittest.IsolatedAsyncioTestCase):
    def make_query(self):
        message = SimpleNamespace(edit_text=AsyncMock())
        query = SimpleNamespace(
            answer=AsyncMock(),
            message=message,
            from_user=SimpleNamespace(id=123),
        )
        return query, message

    def test_confirmation_keyboard_has_confirm_and_cancel_callbacks(self):
        keyboard = build_key_obtained_mailbox_confirmation_keyboard().inline_keyboard

        self.assertEqual("Confirm", keyboard[0][0].text)
        self.assertEqual(
            RECEIVER_MAILBOX_KEY_OBTAINED_CONFIRM_CALLBACK,
            keyboard[0][0].callback_data,
        )
        self.assertEqual("Cancel", keyboard[0][1].text)
        self.assertEqual(
            RECEIVER_MAILBOX_KEY_OBTAINED_CANCEL_CALLBACK,
            keyboard[0][1].callback_data,
        )

    async def test_take_from_mailbox_first_click_only_asks_for_confirmation(self):
        query, message = self.make_query()

        with patch.object(bot, "take_key_from_mailbox") as take_key_from_mailbox:
            await bot.handle_key_obtained_from_mailbox(query, message)

        take_key_from_mailbox.assert_not_called()
        query.answer.assert_awaited_once_with(messages.PLEASE_CONFIRM_KEY_OBTAINED)
        message.edit_text.assert_awaited_once()
        args, kwargs = message.edit_text.call_args
        self.assertEqual((messages.KEY_TAKE_MAILBOX_CONFIRMATION_PROMPT,), args)
        self.assertIn("reply_markup", kwargs)

    async def test_take_from_mailbox_confirm_updates_holder(self):
        query, message = self.make_query()

        with patch.object(
            bot,
            "take_key_from_mailbox",
            return_value=TakeFromMailboxResult(status=TakeFromMailboxStatus.TAKEN),
        ) as take_key_from_mailbox:
            await bot.handle_key_obtained_from_mailbox_confirmation(query, message)

        take_key_from_mailbox.assert_called_once_with(
            bot.DEFAULT_DATABASE_PATH,
            123,
            bot.DEFAULT_KEY_ID,
        )
        query.answer.assert_awaited_once_with()


if __name__ == "__main__":
    unittest.main()
