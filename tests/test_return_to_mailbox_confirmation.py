import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src import bot, messages
from src.key_service import ReturnToMailboxResult, ReturnToMailboxStatus
from src.keyboards import (
    HOLDER_KEY_RETURN_MAILBOX_CANCEL_CALLBACK,
    HOLDER_KEY_RETURN_MAILBOX_CONFIRM_CALLBACK,
    build_key_return_mailbox_confirmation_keyboard,
)


class ReturnToMailboxConfirmationTests(unittest.IsolatedAsyncioTestCase):
    def make_query(self):
        message = SimpleNamespace(edit_text=AsyncMock())
        query = SimpleNamespace(
            answer=AsyncMock(),
            message=message,
            from_user=SimpleNamespace(id=123),
        )
        return query, message

    def test_confirmation_keyboard_has_confirm_and_cancel_callbacks(self):
        keyboard = build_key_return_mailbox_confirmation_keyboard().inline_keyboard

        self.assertEqual("Confirm", keyboard[0][0].text)
        self.assertEqual(
            HOLDER_KEY_RETURN_MAILBOX_CONFIRM_CALLBACK,
            keyboard[0][0].callback_data,
        )
        self.assertEqual("Cancel", keyboard[0][1].text)
        self.assertEqual(
            HOLDER_KEY_RETURN_MAILBOX_CANCEL_CALLBACK,
            keyboard[0][1].callback_data,
        )

    async def test_return_to_mailbox_first_click_only_asks_for_confirmation(self):
        query, message = self.make_query()

        with patch.object(bot, "return_key_to_mailbox") as return_key_to_mailbox:
            await bot.handle_key_return_mailbox(query, message)

        return_key_to_mailbox.assert_not_called()
        query.answer.assert_awaited_once_with()
        message.edit_text.assert_awaited_once()
        args, kwargs = message.edit_text.call_args
        self.assertEqual((messages.MAILBOX_HOLDER_RETURN_PROMPT,), args)
        self.assertIn("reply_markup", kwargs)

    async def test_return_to_mailbox_confirm_updates_holder(self):
        query, message = self.make_query()

        with patch.object(
            bot,
            "return_key_to_mailbox",
            return_value=ReturnToMailboxResult(status=ReturnToMailboxStatus.RETURNED),
        ) as return_key_to_mailbox:
            await bot.handle_key_return_mailbox_confirmation(query, message)

        return_key_to_mailbox.assert_called_once_with(
            bot.DEFAULT_DATABASE_PATH,
            123,
            bot.DEFAULT_KEY_ID,
        )
        query.answer.assert_awaited_once_with()


if __name__ == "__main__":
    unittest.main()
