import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src import bot
from src import messages


class EditMessageFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_callback_edits_existing_message_instead_of_deleting_it(self):
        message = SimpleNamespace(
            delete=AsyncMock(),
            edit_text=AsyncMock(),
        )
        query = SimpleNamespace(
            data="unknown",
            message=message,
            answer=AsyncMock(),
            from_user=None,
        )
        update = SimpleNamespace(callback_query=query)

        await bot.callback_query_handler(update, SimpleNamespace())

        message.delete.assert_not_awaited()
        message.edit_text.assert_awaited_once()
        args, kwargs = message.edit_text.call_args

        self.assertEqual((messages.UNKNOWN_CALLBACK_ANSWER,), args)
        self.assertIn("reply_markup", kwargs)


if __name__ == "__main__":
    unittest.main()
