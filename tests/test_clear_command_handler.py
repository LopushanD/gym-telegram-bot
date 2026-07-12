import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, call, patch

from telegram.error import TelegramError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src import messages
from src.user_command_handlers import clear_command_handler


class ClearCommandHandlerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.message = SimpleNamespace(
            message_id=205,
            reply_text=AsyncMock(),
            edit_text=AsyncMock(),
        )
        self.update = SimpleNamespace(
            effective_message=self.message,
            effective_chat=SimpleNamespace(id=300),
            effective_user=SimpleNamespace(id=123456789),
        )
        self.bot = SimpleNamespace(
            delete_messages=AsyncMock(),
            send_message=AsyncMock(),
        )

    async def test_keeps_clear_command_until_start_state_is_sent(self):
        events = []

        async def delete_messages(**kwargs):
            events.append(("delete", kwargs["message_ids"]))

        async def send_message(**kwargs):
            events.append(("send", kwargs["text"]))

        self.bot.delete_messages.side_effect = delete_messages
        self.bot.send_message.side_effect = send_message

        markup = object()
        with patch("src.bot_replies._build_start_state_markup", return_value=markup):
            await clear_command_handler(self.update, SimpleNamespace(bot=self.bot))

        self.bot.delete_messages.assert_has_awaits(
            [
                call(chat_id=300, message_ids=list(range(105, 205))),
                call(chat_id=300, message_ids=list(range(5, 105))),
                call(chat_id=300, message_ids=list(range(1, 5))),
                call(chat_id=300, message_ids=[205]),
            ],
        )
        self.bot.send_message.assert_awaited_once_with(
            chat_id=300,
            text=messages.START_USER_MENU_TEXT,
            reply_markup=markup,
        )
        self.message.reply_text.assert_not_awaited()
        self.message.edit_text.assert_not_awaited()
        self.assertEqual(
            [
                ("delete", list(range(105, 205))),
                ("delete", list(range(5, 105))),
                ("delete", list(range(1, 5))),
                ("send", messages.START_USER_MENU_TEXT),
                ("delete", [205]),
            ],
            events,
        )

    async def test_sends_start_state_after_stopping_at_undeletable_messages(self):
        self.message.message_id = 2
        self.bot.delete_messages.side_effect = [
            TelegramError("too old"),
            True,
        ]

        with patch("src.bot_replies._build_start_state_markup", return_value=object()):
            await clear_command_handler(self.update, SimpleNamespace(bot=self.bot))

        self.bot.delete_messages.assert_has_awaits(
            [
                call(chat_id=300, message_ids=[1]),
                call(chat_id=300, message_ids=[2]),
            ],
        )
        self.bot.send_message.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
