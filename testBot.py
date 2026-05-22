from collections.abc import Awaitable, Callable
from typing import Final, cast

from telegram import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from database import DEFAULT_DATABASE_PATH, get_current_key_holder, initialize_database

BOT_ID: Final[str] = "t.me/api_test_4398523423043_bot"
KEY_REQUEST_CALLBACK: Final[str] = "key_request"
KEY_OBTAINED_CALLBACK: Final[str] = "key_obtained"
CONFIRM_KEY_OBTAINED_CALLBACK: Final[str] = "confirm_key_obtained"
CANCEL_KEY_OBTAINED_CALLBACK: Final[str] = "cancel_key_obtained"
CallbackHandler = Callable[[CallbackQuery, Message], Awaitable[None]]
START_STATE_TEXT: Final[str] = "Welcome! The buttons are ready."


def build_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("Request the key", callback_data=KEY_REQUEST_CALLBACK)
        ],
        [
            InlineKeyboardButton("Got the key", callback_data=KEY_OBTAINED_CALLBACK)
        ]
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


async def reply_with_start_state(message: Message, text: str = START_STATE_TEXT) -> None:
    await message.reply_text(text, reply_markup=build_keyboard())


async def start_state_command_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if update.message is None:
        return

    await reply_with_start_state(update.message)


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
    holder = get_current_key_holder(DEFAULT_DATABASE_PATH)

    await query.answer("Looking up the key holder...")
    if holder is None:
        await reply_with_start_state(
            message,
            "No key is registered in the database yet.",
        )
        return

    name, surname, room_number = holder
    await reply_with_start_state(
        message,
        f"The key is currently held by {name} {surname}, room {room_number}."
    )


async def handle_key_obtained(query: CallbackQuery, message: Message) -> None:
    await query.answer("Please confirm.")
    await message.reply_text(
        "Please confirm that you got the key.",
        reply_markup=build_key_obtained_confirmation_keyboard(),
    )


async def handle_key_obtained_confirmation(
    query: CallbackQuery,
    message: Message,
) -> None:
    await query.answer("Confirmed.")
    await reply_with_start_state(
        message,
        "Confirmed. The key-obtained action is working.",
    )


async def handle_key_obtained_cancellation(
    query: CallbackQuery,
    message: Message,
) -> None:
    await query.answer("Cancelled.")
    await reply_with_start_state(
        message,
        "Cancelled. No key-obtained action was recorded.",
    )


async def handle_unknown_callback(query: CallbackQuery, message: Message) -> None:
    await query.answer("Unknown button.")
    await reply_with_start_state(message, "Unknown button. Back to the start.")


CALLBACK_HANDLERS: dict[str, CallbackHandler] = {
    KEY_REQUEST_CALLBACK: handle_key_request,
    KEY_OBTAINED_CALLBACK: handle_key_obtained,
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
