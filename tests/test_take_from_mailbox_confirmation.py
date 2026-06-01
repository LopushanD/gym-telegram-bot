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
    RECEIVER_MAILBOX_KEY_CHOICE_CALLBACK_PREFIX,
    RECEIVER_MAILBOX_KEY_OBTAINED_CANCEL_CALLBACK,
    RECEIVER_MAILBOX_KEY_OBTAINED_CONFIRM_CALLBACK,
    RECEIVER_MAILBOX_KEY_OBTAINED_CONFIRM_CALLBACK_PREFIX,
    build_key_obtained_mailbox_confirmation_keyboard,
)


class TakeFromMailboxConfirmationTests(unittest.IsolatedAsyncioTestCase):
    def make_query(self, callback_data=None):
        message = SimpleNamespace(edit_text=AsyncMock(), message_id=10, chat_id=20)
        query = SimpleNamespace(
            answer=AsyncMock(),
            message=message,
            from_user=SimpleNamespace(id=123),
            data=callback_data,
        )
        return query, message

    def test_confirmation_keyboard_has_confirm_and_cancel_callbacks(self):
        keyboard = build_key_obtained_mailbox_confirmation_keyboard(2).inline_keyboard

        self.assertEqual("Confirm", keyboard[0][0].text)
        self.assertEqual(
            f"{RECEIVER_MAILBOX_KEY_OBTAINED_CONFIRM_CALLBACK}:2",
            keyboard[0][0].callback_data,
        )
        self.assertEqual("Cancel", keyboard[0][1].text)
        self.assertEqual(
            RECEIVER_MAILBOX_KEY_OBTAINED_CANCEL_CALLBACK,
            keyboard[0][1].callback_data,
        )

    async def test_take_from_mailbox_first_click_asks_which_key(self):
        query, message = self.make_query()

        with (
            patch.object(bot, "get_key_count", return_value=2) as get_key_count,
            patch.object(bot, "take_key_from_mailbox") as take_key_from_mailbox,
        ):
            await bot.handle_key_obtained_from_mailbox(query, message)

        get_key_count.assert_called_once_with(bot.DEFAULT_DATABASE_PATH)
        take_key_from_mailbox.assert_not_called()
        query.answer.assert_awaited_once_with()
        message.edit_text.assert_awaited_once()
        args, kwargs = message.edit_text.call_args
        self.assertEqual((messages.KEY_CHOICE_PROMPT,), args)
        self.assertIn("reply_markup", kwargs)
        keyboard = kwargs["reply_markup"].inline_keyboard
        self.assertEqual("1", keyboard[0][0].text)
        self.assertEqual("2", keyboard[1][0].text)
        self.assertEqual("Cancel", keyboard[2][0].text)

    async def test_take_from_mailbox_key_choice_asks_for_confirmation(self):
        query, message = self.make_query(
            f"{RECEIVER_MAILBOX_KEY_CHOICE_CALLBACK_PREFIX}:2",
        )

        await bot.handle_key_obtained_from_mailbox_choice(query, message)

        query.answer.assert_awaited_once_with()
        message.edit_text.assert_awaited_once()
        args, kwargs = message.edit_text.call_args
        self.assertEqual((messages.mailbox_receiver_take_prompt(2),), args)
        self.assertIn("reply_markup", kwargs)
        keyboard = kwargs["reply_markup"].inline_keyboard
        self.assertEqual(
            f"{RECEIVER_MAILBOX_KEY_OBTAINED_CONFIRM_CALLBACK_PREFIX}:2",
            keyboard[0][0].callback_data,
        )

    async def test_callback_query_handler_routes_key_choice_callback(self):
        query, message = self.make_query(
            f"{RECEIVER_MAILBOX_KEY_CHOICE_CALLBACK_PREFIX}:2",
        )
        update = SimpleNamespace(callback_query=query)

        with patch.object(
            bot,
            "handle_key_obtained_from_mailbox_choice",
            new_callable=AsyncMock,
        ) as handler:
            await bot.callback_query_handler(update, None)

        handler.assert_awaited_once_with(query, message)

    async def test_callback_query_handler_routes_key_confirmation_callback(self):
        query, message = self.make_query(
            f"{RECEIVER_MAILBOX_KEY_OBTAINED_CONFIRM_CALLBACK_PREFIX}:2",
        )
        update = SimpleNamespace(callback_query=query)

        with patch.object(
            bot,
            "handle_key_obtained_from_mailbox_confirmation",
            new_callable=AsyncMock,
        ) as handler:
            await bot.callback_query_handler(update, None)

        handler.assert_awaited_once_with(query, message)

    async def test_take_from_mailbox_confirm_updates_holder(self):
        query, message = self.make_query(
            f"{RECEIVER_MAILBOX_KEY_OBTAINED_CONFIRM_CALLBACK_PREFIX}:2",
        )

        with patch.object(
            bot,
            "take_key_from_mailbox",
            return_value=TakeFromMailboxResult(status=TakeFromMailboxStatus.TAKEN),
        ) as take_key_from_mailbox, patch.object(
            bot,
            "get_key_owner_mailbox_info",
            return_value=(bot.MAILBOX_MEMBER_ID, 1234),
        ):
            await bot.handle_key_obtained_from_mailbox_confirmation(query, message)

        take_key_from_mailbox.assert_called_once_with(
            bot.DEFAULT_DATABASE_PATH,
            123,
            2,
            bot.MAILBOX_MEMBER_ID,
        )
        query.answer.assert_awaited_once_with()


if __name__ == "__main__":
    unittest.main()
