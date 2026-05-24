import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.keyboards import (
    HOLDER_KEY_RETURN_MAILBOX_CALLBACK,
    build_start_keyboard,
)


class ReturnToMailboxKeyboardTests(unittest.TestCase):
    def test_holder_start_keyboard_has_return_to_mailbox_callback(self):
        keyboard = build_start_keyboard(include_holder_actions=True)

        return_button = keyboard.inline_keyboard[1][0]

        self.assertEqual("Return key to mailbox", return_button.text)
        self.assertEqual(
            HOLDER_KEY_RETURN_MAILBOX_CALLBACK,
            return_button.callback_data,
        )


if __name__ == "__main__":
    unittest.main()
