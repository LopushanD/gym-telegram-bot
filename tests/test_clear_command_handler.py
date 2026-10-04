import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from telegram.error import TelegramError

from src.user_command_handlers import clear_command_handler


class ClearCommandHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_deletes_recent_messages_before_restoring_menu(self):
        message = SimpleNamespace(message_id=205, id=205)
        chat = SimpleNamespace(delete_messages=AsyncMock())
        update = SimpleNamespace(effective_message=message, effective_chat=chat,
                                 effective_user=SimpleNamespace(id=123))
        with patch("src.user_command_handlers.asyncio.sleep", new_callable=AsyncMock), patch(
            "src.user_command_handlers.reply_with_start_state", new_callable=AsyncMock
        ) as reply:
            async def check_deletion(*args, **kwargs):
                chat.delete_messages.assert_awaited_once_with(list(range(115, 206)))
            reply.side_effect = check_deletion
            await clear_command_handler(update, SimpleNamespace())
            reply.assert_awaited_once_with(message, telegram_user_id=123)

    async def test_recent_chat_does_not_request_nonpositive_message_ids(self):
        message = SimpleNamespace(message_id=2, id=2)
        chat = SimpleNamespace(delete_messages=AsyncMock())
        update = SimpleNamespace(effective_message=message, effective_chat=chat)
        with patch("src.user_command_handlers.asyncio.sleep", new_callable=AsyncMock), patch(
            "src.user_command_handlers.reply_with_start_state", new_callable=AsyncMock
        ):
            await clear_command_handler(update, SimpleNamespace())
        chat.delete_messages.assert_awaited_once_with([1, 2])

    async def test_deletion_failure_is_not_reported_as_success(self):
        message = SimpleNamespace(message_id=2, id=2)
        chat = SimpleNamespace(delete_messages=AsyncMock(side_effect=TelegramError("too old")))
        update = SimpleNamespace(effective_message=message, effective_chat=chat)
        with patch("src.user_command_handlers.reply_with_start_state", new_callable=AsyncMock) as reply:
            with self.assertRaises(TelegramError):
                await clear_command_handler(update, SimpleNamespace())
        reply.assert_not_awaited()
