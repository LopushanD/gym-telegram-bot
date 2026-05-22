from typing import Final

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


KEY_REQUEST_CALLBACK: Final[str] = "key_request"
KEY_OBTAINED_CALLBACK: Final[str] = "key_obtained"
KEY_HANDOVER_CALLBACK: Final[str] = "key_handover"
CONFIRM_KEY_OBTAINED_CALLBACK: Final[str] = "confirm_key_obtained"
CANCEL_KEY_OBTAINED_CALLBACK: Final[str] = "cancel_key_obtained"


def build_start_keyboard(include_holder_actions: bool = False) -> InlineKeyboardMarkup:
    if include_holder_actions:
        keyboard = [
            [
                InlineKeyboardButton(
                    "Hand over the key",
                    callback_data=KEY_HANDOVER_CALLBACK,
                )
            ]
        ]
    else:
        keyboard = [
            [
                InlineKeyboardButton("Request the key", callback_data=KEY_REQUEST_CALLBACK)
            ],
            [
                InlineKeyboardButton("Got the key", callback_data=KEY_OBTAINED_CALLBACK)
            ],
        ]
    return InlineKeyboardMarkup(keyboard)


def build_key_obtained_confirmation_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("Confirm", callback_data=CONFIRM_KEY_OBTAINED_CALLBACK),
            InlineKeyboardButton("Cancel", callback_data=CANCEL_KEY_OBTAINED_CALLBACK),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
