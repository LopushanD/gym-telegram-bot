import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, call, patch

from telegram.error import TelegramError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src import messages
from src.user_commands import (
    clear_command_handler,
    my_telegram_id_command_handler,
)


class MyTelegramIdCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_replies_with_requesting_users_telegram_id(self):
        message = SimpleNamespace(reply_text=AsyncMock())
        update = SimpleNamespace(
            effective_message=message,
            effective_user=SimpleNamespace(id=123456789),
        )

        await my_telegram_id_command_handler(update, SimpleNamespace())

        message.reply_text.assert_awaited_once_with(
            messages.MY_TELEGRAM_ID_TEXT.format(telegram_user_id=123456789),
        )

    async def test_reports_when_telegram_user_is_missing(self):
        message = SimpleNamespace(reply_text=AsyncMock())
        update = SimpleNamespace(
            effective_message=message,
            effective_user=None,
        )

        await my_telegram_id_command_handler(update, SimpleNamespace())

        message.reply_text.assert_awaited_once_with(messages.AUTH_USER_MISSING_TEXT)


class ClearCommandTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.message = SimpleNamespace(message_id=205, reply_text=AsyncMock())
        self.update = SimpleNamespace(
            effective_message=self.message,
            effective_chat=SimpleNamespace(id=300, type="private"),
            effective_user=SimpleNamespace(id=123456789),
        )
        self.bot = SimpleNamespace(
            delete_messages=AsyncMock(),
            send_message=AsyncMock(),
        )

    async def test_deletes_private_chat_messages_in_batches_and_returns_start_state(self):
        markup = object()
        with patch(
            "src.user_commands.build_start_state_markup",
            return_value=markup,
        ) as build_markup:
            await clear_command_handler(
                self.update,
                SimpleNamespace(bot=self.bot),
            )

        self.bot.delete_messages.assert_has_awaits(
            [
                call(chat_id=300, message_ids=list(range(106, 206))),
                call(chat_id=300, message_ids=list(range(6, 106))),
                call(chat_id=300, message_ids=list(range(1, 6))),
            ],
        )
        build_markup.assert_called_once_with(123456789)
        self.bot.send_message.assert_awaited_once_with(
            chat_id=300,
            text=messages.START_USER_MENU_TEXT,
            reply_markup=markup,
        )

    async def test_recovers_when_batch_contains_an_undeletable_message(self):
        self.message.message_id = 2
        self.bot.delete_messages.side_effect = [
            TelegramError("batch contains old message"),
            True,
            TelegramError("too old"),
        ]

        with patch(
            "src.user_commands.build_start_state_markup",
            return_value=object(),
        ):
            await clear_command_handler(
                self.update,
                SimpleNamespace(bot=self.bot),
            )

        self.bot.delete_messages.assert_has_awaits(
            [
                call(chat_id=300, message_ids=[1, 2]),
                call(chat_id=300, message_ids=[2]),
                call(chat_id=300, message_ids=[1]),
            ],
        )
        self.bot.send_message.assert_awaited_once()

    async def test_stops_after_an_entire_older_batch_is_undeletable(self):
        self.message.message_id = 101
        with patch(
            "src.user_commands.delete_deletable_messages",
            new=AsyncMock(side_effect=[True, False]),
        ) as delete_deletable:
            with patch("src.user_commands.build_start_state_markup", return_value=object()):
                await clear_command_handler(
                    self.update,
                    SimpleNamespace(bot=self.bot),
                )

        self.assertEqual(2, delete_deletable.await_count)
        self.bot.send_message.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
