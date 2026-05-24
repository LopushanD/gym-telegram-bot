from typing import Final

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

RECEIVER_KEY_INFO_CALLBACK: Final[str] = "receiver_key_info"
HOLDER_KEY_HANDOVER_CALLBACK: Final[str] = "holder_key_handover"
RECEIVER_HANDOVER_KEY_OBTAINED_CALLBACK: Final[str] = "handover_receiver_key_obtained"
KEY_HANDOVER_RECEIVER_CONFIRMATION_CALLBACK: Final[str] = "handover_receiver_confirm_key_obtained"
RECEIVER_KEY_HANDOVER_CANCEL_CALLBACK: Final[str] = "handover_receiver_cancel_key_obtained"
HOLDER_KEY_HANDOVER_CANCEL_CALLBACK: Final[str] = "handover_holder_cancel_key_obtained"


def build_start_keyboard(include_holder_actions: bool = False) -> InlineKeyboardMarkup:
    if include_holder_actions:
        keyboard = [
            [
                InlineKeyboardButton(
                    "Hand over the key",
                    callback_data=HOLDER_KEY_HANDOVER_CALLBACK,
                )
            ]
        ]
    else:
        keyboard = [
            [
                InlineKeyboardButton("Request the key", callback_data=RECEIVER_KEY_INFO_CALLBACK)
            ],
            [
                InlineKeyboardButton("Got the key", callback_data=RECEIVER_HANDOVER_KEY_OBTAINED_CALLBACK)
            ],
        ]
    return InlineKeyboardMarkup(keyboard)

def build_key_handover_holder_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("Cancel", callback_data=HOLDER_KEY_HANDOVER_CANCEL_CALLBACK)
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_key_obtained_receiver_confirmation_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("Confirm", callback_data=KEY_HANDOVER_RECEIVER_CONFIRMATION_CALLBACK),
            InlineKeyboardButton("Cancel", callback_data=RECEIVER_KEY_HANDOVER_CANCEL_CALLBACK),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
