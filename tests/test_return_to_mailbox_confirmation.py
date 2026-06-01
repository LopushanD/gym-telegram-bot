import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src import bot, messages
from src.key_service import KeyReturnInstruction
from src.key_service import ReturnToMailboxResult, ReturnToMailboxStatus
from src.keyboards import (
    HOLDER_KEY_RETURN_MAILBOX_CANCEL_CALLBACK,
    HOLDER_KEY_RETURN_MAILBOX_CONFIRM_CALLBACK,
    HOLDER_KEY_RETURN_MAILBOX_CONFIRM_CALLBACK_PREFIX,
    HOLDER_KEY_RETURN_MAILBOX_KEY_CHOICE_CALLBACK_PREFIX,
    build_key_return_mailbox_confirmation_keyboard,
    build_key_return_mailbox_returned_keyboard,
)


class ReturnToMailboxConfirmationTests(unittest.IsolatedAsyncioTestCase):
    def make_query(self, callback_data=None):
        message = SimpleNamespace(edit_text=AsyncMock())
        query = SimpleNamespace(
            answer=AsyncMock(),
            message=message,
            from_user=SimpleNamespace(id=123),
            data=callback_data,
        )
        return query, message

    def test_confirmation_keyboard_has_confirm_and_cancel_callbacks(self):
        keyboard = build_key_return_mailbox_confirmation_keyboard(2).inline_keyboard

        self.assertEqual("Confirm", keyboard[0][0].text)
        self.assertEqual(
            f"{HOLDER_KEY_RETURN_MAILBOX_CONFIRM_CALLBACK}:2",
            keyboard[0][0].callback_data,
        )
        self.assertEqual("Cancel", keyboard[0][1].text)
        self.assertEqual(
            HOLDER_KEY_RETURN_MAILBOX_CANCEL_CALLBACK,
            keyboard[0][1].callback_data,
        )

    def test_returned_keyboard_has_returned_and_cancel_callbacks(self):
        keyboard = build_key_return_mailbox_returned_keyboard(2)

        rows = keyboard.inline_keyboard

        self.assertEqual(2, len(rows))
        self.assertEqual("Returned", rows[0][0].text)
        self.assertEqual(
            f"{HOLDER_KEY_RETURN_MAILBOX_KEY_CHOICE_CALLBACK_PREFIX}:2",
            rows[0][0].callback_data,
        )
        self.assertEqual("Cancel", rows[1][0].text)
        self.assertEqual(HOLDER_KEY_RETURN_MAILBOX_CANCEL_CALLBACK, rows[1][0].callback_data)

    async def test_return_to_mailbox_first_click_shows_return_instruction(self):
        query, message = self.make_query()

        with (
            patch.object(
                bot,
                "get_key_return_instruction",
                return_value=KeyReturnInstruction(key_id=2, room_number=1234),
            ) as get_key_return_instruction,
            patch.object(bot, "return_key_to_mailbox") as return_key_to_mailbox,
        ):
            await bot.handle_key_return_mailbox(query, message)

        get_key_return_instruction.assert_called_once_with(bot.DEFAULT_DATABASE_PATH, 123)
        return_key_to_mailbox.assert_not_called()
        query.answer.assert_awaited_once_with()
        message.edit_text.assert_awaited_once()
        args, kwargs = message.edit_text.call_args
        self.assertEqual(
            (
                messages.MAILBOX_HOLDER_RETURN_INSTRUCTION_TEXT.format(
                    key_id=2,
                    room_number=1234,
                ),
            ),
            args,
        )
        self.assertIn("reply_markup", kwargs)
        keyboard = kwargs["reply_markup"].inline_keyboard
        self.assertEqual("Returned", keyboard[0][0].text)
        self.assertEqual("Cancel", keyboard[1][0].text)

    async def test_return_to_mailbox_first_click_blocks_without_return_instruction(self):
        query, message = self.make_query()

        with patch.object(bot, "get_key_return_instruction", return_value=None):
            await bot.handle_key_return_mailbox(query, message)

        query.answer.assert_awaited_once_with()
        message.edit_text.assert_awaited_once()
        args, _ = message.edit_text.call_args
        self.assertEqual((messages.MAILBOX_HOLDER_BLOCKED_TEXT,), args)

    async def test_return_to_mailbox_key_choice_asks_for_confirmation(self):
        query, message = self.make_query(
            f"{HOLDER_KEY_RETURN_MAILBOX_KEY_CHOICE_CALLBACK_PREFIX}:2",
        )

        await bot.handle_key_return_mailbox_choice(query, message)

        query.answer.assert_awaited_once_with()
        message.edit_text.assert_awaited_once()
        args, kwargs = message.edit_text.call_args
        self.assertEqual(
            (messages.MAILBOX_HOLDER_RETURN_PROMPT.format(key_id=2),),
            args,
        )
        self.assertIn("reply_markup", kwargs)
        keyboard = kwargs["reply_markup"].inline_keyboard
        self.assertEqual(
            f"{HOLDER_KEY_RETURN_MAILBOX_CONFIRM_CALLBACK_PREFIX}:2",
            keyboard[0][0].callback_data,
        )

    async def test_callback_query_handler_routes_key_choice_callback(self):
        query, message = self.make_query(
            f"{HOLDER_KEY_RETURN_MAILBOX_KEY_CHOICE_CALLBACK_PREFIX}:2",
        )
        update = SimpleNamespace(callback_query=query)

        with patch.object(
            bot,
            "handle_key_return_mailbox_choice",
            new_callable=AsyncMock,
        ) as handler:
            await bot.callback_query_handler(update, None)

        handler.assert_awaited_once_with(query, message)

    async def test_callback_query_handler_routes_key_confirmation_callback(self):
        query, message = self.make_query(
            f"{HOLDER_KEY_RETURN_MAILBOX_CONFIRM_CALLBACK_PREFIX}:2",
        )
        update = SimpleNamespace(callback_query=query)

        with patch.object(
            bot,
            "handle_key_return_mailbox_confirmation",
            new_callable=AsyncMock,
        ) as handler:
            await bot.callback_query_handler(update, None)

        handler.assert_awaited_once_with(query, message)

    async def test_return_to_mailbox_confirm_updates_holder(self):
        query, message = self.make_query(
            f"{HOLDER_KEY_RETURN_MAILBOX_CONFIRM_CALLBACK_PREFIX}:2",
        )

        with patch.object(
            bot,
            "return_key_to_mailbox",
            return_value=ReturnToMailboxResult(status=ReturnToMailboxStatus.RETURNED),
        ) as return_key_to_mailbox:
            await bot.handle_key_return_mailbox_confirmation(query, message)

        return_key_to_mailbox.assert_called_once_with(
            bot.DEFAULT_DATABASE_PATH,
            123,
            2,
        )
        query.answer.assert_awaited_once_with()


if __name__ == "__main__":
    unittest.main()
