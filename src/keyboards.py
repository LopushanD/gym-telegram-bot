from typing import Final

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

RECEIVER_KEY_INFO_CALLBACK: Final[str] = "receiver_key_info"
HOLDER_KEY_HANDOVER_CALLBACK: Final[str] = "holder_key_handover"
RECEIVER_HANDOVER_KEY_OBTAINED_CALLBACK: Final[str] = "handover_receiver_key_obtained"
RECEIVER_HANDOVER_KEY_CHOICE_CALLBACK_PREFIX: Final[str] = "handover_receiver_key_choice"
RECEIVER_MAILBOX_KEY_OBTAINED_CALLBACK: Final[str] = "mailbox_receiver_key_obtained"
RECEIVER_MAILBOX_KEY_CHOICE_CALLBACK_PREFIX: Final[str] = "mailbox_receiver_key_choice"
# RECEIVER_MAILBOX_KEY_CHOICE_CALLBACK: Final[str] = RECEIVER_MAILBOX_KEY_CHOICE_CALLBACK_PREFIX
RECEIVER_MAILBOX_KEY_OBTAINED_CONFIRM_CALLBACK_PREFIX: Final[str] = (
    "mailbox_receiver_confirm_key_obtained"
)
RECEIVER_MAILBOX_KEY_OBTAINED_CONFIRM_CALLBACK: Final[str] = (
    RECEIVER_MAILBOX_KEY_OBTAINED_CONFIRM_CALLBACK_PREFIX
)
RECEIVER_MAILBOX_KEY_OBTAINED_CANCEL_CALLBACK: Final[str] = "mailbox_receiver_cancel_key_obtained"
RECEIVER_KEY_HANDOVER_CONFIRM_CALLBACK: Final[str] = "handover_receiver_confirm_key_obtained"
RECEIVER_KEY_HANDOVER_CANCEL_CALLBACK: Final[str] = "handover_receiver_cancel_key_obtained"
HOLDER_KEY_HANDOVER_CANCEL_CALLBACK: Final[str] = "handover_holder_cancel_key_obtained"
HOLDER_KEY_RETURN_MAILBOX_CALLBACK: Final[str] = "holder_key_return_mailbox"
HOLDER_KEY_RETURN_MAILBOX_KEY_CHOICE_CALLBACK_PREFIX: Final[str] = (
    "holder_key_return_mailbox_choice"
)
HOLDER_KEY_RETURN_MAILBOX_CONFIRM_CALLBACK_PREFIX: Final[str] = (
    "holder_key_return_mailbox_confirm"
)
HOLDER_KEY_RETURN_MAILBOX_CANCEL_CALLBACK: Final[str] = "holder_key_return_mailbox_cancel"


def mailbox_key_choice_callback(key_id: int) -> str:
    return f"{RECEIVER_MAILBOX_KEY_CHOICE_CALLBACK_PREFIX}:{key_id}"


def handover_key_choice_callback(key_id: int) -> str:
    return f"{RECEIVER_HANDOVER_KEY_CHOICE_CALLBACK_PREFIX}:{key_id}"


def mailbox_key_obtained_confirm_callback(key_id: int) -> str:
    return f"{RECEIVER_MAILBOX_KEY_OBTAINED_CONFIRM_CALLBACK_PREFIX}:{key_id}"


def handover_key_obtained_confirm_callback(key_id: int) -> str:
    return f"{RECEIVER_KEY_HANDOVER_CONFIRM_CALLBACK}:{key_id}"


def mailbox_key_return_choice_callback(key_id: int) -> str:
    return f"{HOLDER_KEY_RETURN_MAILBOX_KEY_CHOICE_CALLBACK_PREFIX}:{key_id}"


def mailbox_key_return_confirm_callback(key_id: int) -> str:
    return f"{HOLDER_KEY_RETURN_MAILBOX_CONFIRM_CALLBACK_PREFIX}:{key_id}"


def callback_matches_prefix(callback_data: str | None, prefix: str) -> bool:
    return callback_data is not None and callback_data.startswith(f"{prefix}:")


def parse_key_id_callback(callback_data: str, prefix: str) -> int:
    expected_prefix = f"{prefix}:"
    if not callback_data.startswith(expected_prefix):
        raise ValueError(f"callback data does not start with {expected_prefix}")
    return int(callback_data.removeprefix(expected_prefix))


def build_start_keyboard(include_holder_actions: bool = False) -> InlineKeyboardMarkup:
    if include_holder_actions:
        keyboard = [
            [
                InlineKeyboardButton(
                    "Hand key over",
                    callback_data=HOLDER_KEY_HANDOVER_CALLBACK)
            ],
            [
                InlineKeyboardButton(
                    "Return key to mailbox",
                    callback_data=HOLDER_KEY_RETURN_MAILBOX_CALLBACK)
            ]
        ]
    else:
        keyboard = [
            [
                InlineKeyboardButton("Key holder info", callback_data=RECEIVER_KEY_INFO_CALLBACK)
            ],
            [
                InlineKeyboardButton("Got key from member", callback_data=RECEIVER_HANDOVER_KEY_OBTAINED_CALLBACK),
                InlineKeyboardButton("Got key from mailbox", callback_data=RECEIVER_MAILBOX_KEY_OBTAINED_CALLBACK),
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

def build_key_obtained_receiver_confirmation_keyboard(key_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "Confirm",
                callback_data=handover_key_obtained_confirm_callback(key_id),
            ),
            InlineKeyboardButton("Cancel", callback_data=RECEIVER_KEY_HANDOVER_CANCEL_CALLBACK),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def build_key_obtained_receiver_key_choice_keyboard(key_count: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                str(key_id),
                callback_data=handover_key_choice_callback(key_id),
            )
        ]
        for key_id in range(1, key_count + 1)
    ]
    keyboard.append(
        [
            InlineKeyboardButton(
                "Cancel",
                callback_data=RECEIVER_KEY_HANDOVER_CANCEL_CALLBACK,
            )
        ]
    )
    return InlineKeyboardMarkup(keyboard)

def build_key_return_mailbox_confirmation_keyboard(key_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "Confirm",
                callback_data=mailbox_key_return_confirm_callback(key_id),
            ),
            InlineKeyboardButton("Cancel", callback_data=HOLDER_KEY_RETURN_MAILBOX_CANCEL_CALLBACK),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_key_return_mailbox_returned_keyboard(key_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "Returned",
                callback_data=mailbox_key_return_choice_callback(key_id),
            )
        ],
        [
            InlineKeyboardButton(
                "Cancel",
                callback_data=HOLDER_KEY_RETURN_MAILBOX_CANCEL_CALLBACK,
            )
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

def build_key_obtained_mailbox_confirmation_keyboard(key_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "Confirm",
                callback_data=mailbox_key_obtained_confirm_callback(key_id),
            ),
            InlineKeyboardButton("Cancel", callback_data=RECEIVER_MAILBOX_KEY_OBTAINED_CANCEL_CALLBACK),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def build_key_obtained_mailbox_key_choice_keyboard(
    #TODO: make sure IDs are always consisted with IDs in database
    key_count: int,
) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                str(key_id),
                callback_data=mailbox_key_choice_callback(key_id),
            )
        ]
        for key_id in range(1, key_count + 1)
    ]
    keyboard.append(
        [
            InlineKeyboardButton(
                "Cancel",
                callback_data=RECEIVER_MAILBOX_KEY_OBTAINED_CANCEL_CALLBACK,
            )
        ]
    )
    return InlineKeyboardMarkup(keyboard)
