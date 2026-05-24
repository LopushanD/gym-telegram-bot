import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.keyboards import (
    RECEIVER_MAILBOX_KEY_OBTAINED_CALLBACK,
    build_start_keyboard,
)


class TakeFromMailboxKeyboardTests(unittest.TestCase):
    def test_receiver_start_keyboard_has_take_from_mailbox_callback(self):
        keyboard = build_start_keyboard(include_holder_actions=False)

        mailbox_button = keyboard.inline_keyboard[1][1]

        self.assertEqual("Got key from mailbox", mailbox_button.text)
        self.assertEqual(
            RECEIVER_MAILBOX_KEY_OBTAINED_CALLBACK,
            mailbox_button.callback_data,
        )


if __name__ == "__main__":
    unittest.main()
