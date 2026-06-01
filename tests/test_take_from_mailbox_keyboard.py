import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.keyboards import (
    RECEIVER_MAILBOX_KEY_CHOICE_CALLBACK_PREFIX,
    RECEIVER_MAILBOX_KEY_OBTAINED_CALLBACK,
    build_key_obtained_mailbox_key_choice_keyboard,
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

    def test_key_choice_keyboard_has_one_button_per_tracked_key(self):
        keyboard = build_key_obtained_mailbox_key_choice_keyboard(3)

        rows = keyboard.inline_keyboard

        self.assertEqual(4, len(rows))
        self.assertEqual("1", rows[0][0].text)
        self.assertEqual(
            f"{RECEIVER_MAILBOX_KEY_CHOICE_CALLBACK_PREFIX}:1",
            rows[0][0].callback_data,
        )
        self.assertEqual("2", rows[1][0].text)
        self.assertEqual(
            f"{RECEIVER_MAILBOX_KEY_CHOICE_CALLBACK_PREFIX}:2",
            rows[1][0].callback_data,
        )
        self.assertEqual("3", rows[2][0].text)
        self.assertEqual(
            f"{RECEIVER_MAILBOX_KEY_CHOICE_CALLBACK_PREFIX}:3",
            rows[2][0].callback_data,
        )
        self.assertEqual("Cancel", rows[3][0].text)


if __name__ == "__main__":
    unittest.main()
