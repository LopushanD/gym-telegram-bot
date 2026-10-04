import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src import messages
from src.admin_commands import load_command_documentation, ALL_COMMANDS_ADMIN_COMMAND
from src.admin_command_handlers import get_all_commands_handler
from src.models import GymMember
from src.user_command_handlers import (
    get_key_tutorial_command_handler,
    give_key_tutorial_command_handler,
    help_command_handler,
    my_telegram_id_command_handler,
    return_key_tutorial_command_handler,
    tutorials_tutorial_command_handler,
    user_regestration_tutorial_command_handler,
)
from src.user_commands import (
    HELP_TEXT,
    GET_KEY_TUTORIAL,
    GIVE_KEY_TUTORIAL,
    REGESTRATION_TUTORIAL,
    RETURN_KEY_TUTORIAL,
    TUTORIALS_INFO_TUTORIAL,
    load_user_tutorial,
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


class TutorialCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_replies_with_tutorial_overview(self):
        message = SimpleNamespace(reply_text=AsyncMock())
        update = SimpleNamespace(effective_message=message)

        await tutorials_tutorial_command_handler(update, SimpleNamespace())

        message.reply_text.assert_awaited_once_with(
            load_user_tutorial(TUTORIALS_INFO_TUTORIAL),
            parse_mode="MarkdownV2",
        )

    async def test_replies_with_registration_tutorial(self):
        message = SimpleNamespace(reply_text=AsyncMock())
        update = SimpleNamespace(effective_message=message)

        await user_regestration_tutorial_command_handler(update, SimpleNamespace())

        message.reply_text.assert_awaited_once_with(
            load_user_tutorial(REGESTRATION_TUTORIAL),
            parse_mode="MarkdownV2",
        )

    async def test_replies_with_get_key_tutorial(self):
        message = SimpleNamespace(reply_text=AsyncMock())
        update = SimpleNamespace(effective_message=message)

        await get_key_tutorial_command_handler(update, SimpleNamespace())

        message.reply_text.assert_awaited_once_with(
            load_user_tutorial(GET_KEY_TUTORIAL),
            parse_mode="MarkdownV2",
        )

    async def test_replies_with_give_key_tutorial(self):
        message = SimpleNamespace(reply_text=AsyncMock())
        update = SimpleNamespace(effective_message=message)

        await give_key_tutorial_command_handler(update, SimpleNamespace())

        message.reply_text.assert_awaited_once_with(
            load_user_tutorial(GIVE_KEY_TUTORIAL),
            parse_mode="MarkdownV2",
        )

    async def test_replies_with_return_key_tutorial(self):
        message = SimpleNamespace(reply_text=AsyncMock())
        update = SimpleNamespace(effective_message=message)

        await return_key_tutorial_command_handler(update, SimpleNamespace())

        message.reply_text.assert_awaited_once_with(
            load_user_tutorial(RETURN_KEY_TUTORIAL),
            parse_mode="MarkdownV2",
        )


class CommandDocumentationTests(unittest.IsolatedAsyncioTestCase):
    async def test_commands_replies_with_command_documentation(self):
        message = SimpleNamespace(reply_text=AsyncMock())
        update = SimpleNamespace(effective_message=message)

        with patch("src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                   return_value=GymMember(is_admin=True)):
            await get_all_commands_handler(update, SimpleNamespace())

        message.reply_text.assert_awaited_once_with(
            load_command_documentation(ALL_COMMANDS_ADMIN_COMMAND),
            parse_mode="MarkdownV2",
        )

    async def test_help_replies_with_command_documentation_for_compatibility(self):
        message = SimpleNamespace(reply_text=AsyncMock())
        update = SimpleNamespace(effective_message=message)

        await help_command_handler(update, SimpleNamespace())

        message.reply_text.assert_awaited_once_with(
            HELP_TEXT,
            parse_mode="MarkdownV2",
        )


if __name__ == "__main__":
    unittest.main()
