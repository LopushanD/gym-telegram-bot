from collections.abc import Awaitable, Callable
from typing import Final, cast

from telegram import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from database import (
    DEFAULT_DATABASE_PATH,
    get_current_key_holder,
    get_gym_member_id_by_telegram_user_id,
    initialize_database,
    on_holder_change,
)

BOT_ID: Final[str] = "t.me/api_test_4398523423043_bot"
KEY_REQUEST_CALLBACK: Final[str] = "key_request"
KEY_OBTAINED_CALLBACK: Final[str] = "key_obtained"
KEY_HANDOVER_CALLBACK: Final[str] = "key_handover"
CONFIRM_KEY_OBTAINED_CALLBACK: Final[str] = "confirm_key_obtained"
CANCEL_KEY_OBTAINED_CALLBACK: Final[str] = "cancel_key_obtained"
CallbackHandler = Callable[[CallbackQuery, Message], Awaitable[None]]
START_STATE_TEXT: Final[str] = "Welcome! The buttons are ready."
DEFAULT_KEY_ID: Final[int] = 1


def build_keyboard(include_holder_actions: bool = False) -> InlineKeyboardMarkup:
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


def user_currently_holds_key(telegram_user_id: int | None) -> bool:
    if telegram_user_id is None:
        return False

    return get_current_key_holder(
        DEFAULT_DATABASE_PATH,
        key_id=DEFAULT_KEY_ID,
        telegram_user_id=telegram_user_id,
    ) is not None


def get_update_user_id(update: Update) -> int | None:
    user = getattr(update, "effective_user", None)
    if user is None:
        return None

    return user.id


def get_callback_user_id(query: CallbackQuery) -> int | None:
    user = getattr(query, "from_user", None)
    if user is None:
        return None

    return user.id


async def reply_with_start_state(
    message: Message,
    text: str = START_STATE_TEXT,
    telegram_user_id: int | None = None,
) -> None:
    await message.reply_text(
        text,
        reply_markup=build_keyboard(
            include_holder_actions=user_currently_holds_key(telegram_user_id),
        ),
    )


async def start_state_command_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if update.message is None:
        return

    await reply_with_start_state(
        update.message,
        telegram_user_id=get_update_user_id(update),
    )


async def request_key_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.message is None:
        return

    message = cast(Message, query.message)
    await message.delete()

    callback_data = query.data if isinstance(query.data, str) else None
    handler = CALLBACK_HANDLERS.get(callback_data, handle_unknown_callback)
    await handler(query, message)


async def handle_key_request(query: CallbackQuery, message: Message) -> None:
    holder = get_current_key_holder(DEFAULT_DATABASE_PATH, key_id=DEFAULT_KEY_ID)

    await query.answer("Looking up the key holder...")
    if holder is None:
        await reply_with_start_state(
            message,
            "No key is registered in the database yet.",
            telegram_user_id=get_callback_user_id(query),
        )
        return

    name, surname, room_number = holder
    await reply_with_start_state(
        message,
        f"The key is currently held by {name} {surname}, room {room_number}.",
        telegram_user_id=get_callback_user_id(query),
    )


async def handle_key_obtained(query: CallbackQuery, message: Message) -> None:
    await query.answer("Please confirm.")
    await message.reply_text(
        "Please confirm that you got the key.",
        reply_markup=build_key_obtained_confirmation_keyboard(),
    )


async def handle_key_handover(query: CallbackQuery, message: Message) -> None:
    telegram_user_id = get_callback_user_id(query)
    if not user_currently_holds_key(telegram_user_id):
        await query.answer("Only the current holder can hand over the key.")
        await reply_with_start_state(
            message,
            "Only the current key holder can start a handover.",
            telegram_user_id=telegram_user_id,
        )
        return

    await query.answer("Ready for handover.")
    await reply_with_start_state(
        message,
        "Give the key to the next member and ask them to press Got the key.",
        telegram_user_id=telegram_user_id,
    )


async def handle_key_obtained_confirmation(
    query: CallbackQuery,
    message: Message,
) -> None:
    telegram_user_id = get_callback_user_id(query)
    if telegram_user_id is None:
        await query.answer("Could not identify you.")
        await reply_with_start_state(
            message,
            "Could not confirm key ownership because Telegram user is missing.",
        )
        return

    member_id = get_gym_member_id_by_telegram_user_id(
        DEFAULT_DATABASE_PATH,
        telegram_user_id,
    )
    if member_id is None:
        await query.answer("You are not registered.")
        await reply_with_start_state(
            message,
            "Could not confirm key ownership because you are not registered.",
            telegram_user_id=telegram_user_id,
        )
        return

    on_holder_change(DEFAULT_DATABASE_PATH, DEFAULT_KEY_ID, member_id)

    await query.answer("Confirmed.")
    await reply_with_start_state(
        message,
        "Confirmed. You are now recorded as the key holder.",
        telegram_user_id=telegram_user_id,
    )


async def handle_key_obtained_cancellation(
    query: CallbackQuery,
    message: Message,
) -> None:
    await query.answer("Cancelled.")
    await reply_with_start_state(
        message,
        "Cancelled. No key-obtained action was recorded.",
        telegram_user_id=get_callback_user_id(query),
    )


async def handle_unknown_callback(query: CallbackQuery, message: Message) -> None:
    await query.answer("Unknown button.")
    await reply_with_start_state(
        message,
        "Unknown button. Back to the start.",
        telegram_user_id=get_callback_user_id(query),
    )


CALLBACK_HANDLERS: dict[str, CallbackHandler] = {
    KEY_REQUEST_CALLBACK: handle_key_request,
    KEY_OBTAINED_CALLBACK: handle_key_obtained,
    KEY_HANDOVER_CALLBACK: handle_key_handover,
    CONFIRM_KEY_OBTAINED_CALLBACK: handle_key_obtained_confirmation,
    CANCEL_KEY_OBTAINED_CALLBACK: handle_key_obtained_cancellation,
}


def main() -> None:
    """
    Handles the initial launch of the program (entry point).
    """
    token = "REMOVED_TELEGRAM_BOT_TOKEN"
    initialize_database(DEFAULT_DATABASE_PATH)
    application = Application.builder().token(token).concurrent_updates(True).read_timeout(30).write_timeout(30).build()
    
    application.add_handler(CommandHandler("start", start_state_command_handler))
    application.add_handler(CallbackQueryHandler(request_key_handler))
    print("Telegram Bot started!", flush=True)
    application.run_polling()

if __name__ == '__main__':
    main()
