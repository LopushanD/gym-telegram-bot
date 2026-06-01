import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src import bot, messages
from src.keyboards import (
    RECEIVER_KEY_HANDOVER_CONFIRM_CALLBACK,
    RECEIVER_HANDOVER_KEY_CHOICE_CALLBACK_PREFIX,
    RECEIVER_KEY_HANDOVER_CANCEL_CALLBACK,
    build_key_obtained_receiver_confirmation_keyboard,
    build_key_obtained_receiver_key_choice_keyboard,
)


class HandoverReceiverKeyChoiceTests(unittest.IsolatedAsyncioTestCase):
    def make_query(self, callback_data=None):
        message = SimpleNamespace(edit_text=AsyncMock(), message_id=10, chat_id=20)
        query = SimpleNamespace(
            answer=AsyncMock(),
            message=message,
            from_user=SimpleNamespace(id=123),
            data=callback_data,
        )
        return query, message

    def test_key_choice_keyboard_has_one_button_per_tracked_key(self):
        keyboard = build_key_obtained_receiver_key_choice_keyboard(3)

        rows = keyboard.inline_keyboard

        self.assertEqual(4, len(rows))
        self.assertEqual("1", rows[0][0].text)
        self.assertEqual(
            f"{RECEIVER_HANDOVER_KEY_CHOICE_CALLBACK_PREFIX}:1",
            rows[0][0].callback_data,
        )
        self.assertEqual("2", rows[1][0].text)
        self.assertEqual(
            f"{RECEIVER_HANDOVER_KEY_CHOICE_CALLBACK_PREFIX}:2",
            rows[1][0].callback_data,
        )
        self.assertEqual("3", rows[2][0].text)
        self.assertEqual(
            f"{RECEIVER_HANDOVER_KEY_CHOICE_CALLBACK_PREFIX}:3",
            rows[2][0].callback_data,
        )
        self.assertEqual("Cancel", rows[3][0].text)
        self.assertEqual(
            RECEIVER_KEY_HANDOVER_CANCEL_CALLBACK,
            rows[3][0].callback_data,
        )

    def test_confirmation_keyboard_includes_selected_key_id(self):
        keyboard = build_key_obtained_receiver_confirmation_keyboard(2).inline_keyboard

        self.assertEqual("Confirm", keyboard[0][0].text)
        self.assertEqual(
            f"{RECEIVER_KEY_HANDOVER_CONFIRM_CALLBACK}:2",
            keyboard[0][0].callback_data,
        )
        self.assertEqual("Cancel", keyboard[0][1].text)
        self.assertEqual(
            RECEIVER_KEY_HANDOVER_CANCEL_CALLBACK,
            keyboard[0][1].callback_data,
        )

    async def test_first_click_asks_which_key(self):
        query, message = self.make_query()

        with (
            patch.object(bot, "get_key_count", return_value=2) as get_key_count,
            patch.object(bot, "handle_pending_handover_obtained_backend") as backend,
        ):
            await bot.handle_key_obtained(query, message)

        get_key_count.assert_called_once_with(bot.DEFAULT_DATABASE_PATH)
        backend.assert_not_called()
        query.answer.assert_awaited_once_with()
        message.edit_text.assert_awaited_once()
        args, kwargs = message.edit_text.call_args
        self.assertEqual((messages.KEY_CHOICE_PROMPT,), args)
        self.assertIn("reply_markup", kwargs)
        keyboard = kwargs["reply_markup"].inline_keyboard
        self.assertEqual("1", keyboard[0][0].text)
        self.assertEqual("2", keyboard[1][0].text)
        self.assertEqual("Cancel", keyboard[2][0].text)

    async def test_key_choice_uses_selected_key_for_handover_lookup(self):
        query, message = self.make_query(
            f"{RECEIVER_HANDOVER_KEY_CHOICE_CALLBACK_PREFIX}:2",
        )

        with patch.object(
            bot,
            "handle_pending_handover_obtained_backend",
            new_callable=AsyncMock,
        ) as backend:
            await bot.handle_key_obtained_choice(query, message)

        query.answer.assert_awaited_once_with()
        backend.assert_awaited_once_with(
            2,
            query,
            message,
            bot.edit_to_start_state,
        )

    async def test_confirmation_uses_selected_key(self):
        query, message = self.make_query(
            f"{RECEIVER_KEY_HANDOVER_CONFIRM_CALLBACK}:2",
        )

        with patch.object(
            bot,
            "handle_pending_handover_confirmation",
            new_callable=AsyncMock,
        ) as confirmation:
            await bot.handle_key_obtained_confirmation(query, message)

        query.answer.assert_awaited_once_with()
        confirmation.assert_awaited_once_with(
            2,
            query,
            message,
            bot.edit_to_start_state,
        )

    async def test_callback_query_handler_routes_key_choice_callback(self):
        query, message = self.make_query(
            f"{RECEIVER_HANDOVER_KEY_CHOICE_CALLBACK_PREFIX}:2",
        )
        update = SimpleNamespace(callback_query=query)

        with patch.object(
            bot,
            "handle_key_obtained_choice",
            new_callable=AsyncMock,
        ) as handler:
            await bot.callback_query_handler(update, None)

        handler.assert_awaited_once_with(query, message)

    async def test_callback_query_handler_routes_key_confirmation_callback(self):
        query, message = self.make_query(
            f"{RECEIVER_KEY_HANDOVER_CONFIRM_CALLBACK}:2",
        )
        update = SimpleNamespace(callback_query=query)

        with patch.object(
            bot,
            "handle_key_obtained_confirmation",
            new_callable=AsyncMock,
        ) as handler:
            await bot.callback_query_handler(update, None)

        handler.assert_awaited_once_with(query, message)


if __name__ == "__main__":
    unittest.main()
