from collections.abc import Awaitable, Callable
from typing import Final, cast

from telegram import CallbackQuery, Message, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from buttons import (
    CANCEL_KEY_OBTAINED_CALLBACK,
    CONFIRM_KEY_OBTAINED_CALLBACK,
    KEY_HANDOVER_CALLBACK,
    KEY_OBTAINED_CALLBACK,
    KEY_REQUEST_CALLBACK,
    build_key_obtained_confirmation_keyboard,
    build_start_keyboard,
)
from config import BOT_TOKEN, DEFAULT_DATABASE_PATH, DEFAULT_KEY_ID
from database import initialize_database
from key_service import (
    ConfirmKeyStatus,
    HandoverStatus,
    confirm_key_obtained,
    get_key_holder,
    start_key_handover,
    user_currently_holds_key,
)


CallbackHandler = Callable[[CallbackQuery, Message], Awaitable[None]]
START_STATE_TEXT: Final[str] = "Welcome! The buttons are ready."


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
        reply_markup=build_start_keyboard(
            include_holder_actions=user_currently_holds_key(
                DEFAULT_DATABASE_PATH,
                telegram_user_id,
                DEFAULT_KEY_ID,
            ),
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


async def callback_query_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    query = update.callback_query
    if query is None or query.message is None:
        return

    message = cast(Message, query.message)
    await message.delete()

    callback_data = query.data if isinstance(query.data, str) else None
    handler = CALLBACK_HANDLERS.get(callback_data, handle_unknown_callback)
    await handler(query, message)


async def handle_key_request(query: CallbackQuery, message: Message) -> None:
    holder = get_key_holder(DEFAULT_DATABASE_PATH, key_id=DEFAULT_KEY_ID)

    await query.answer("Looking up the key holder...")
    if holder is None:
        await reply_with_start_state(
            message,
            "No key is registered in the database yet.",
            telegram_user_id=get_callback_user_id(query),
        )
        return

    await reply_with_start_state(
        message,
        (
            f"The key is currently held by {holder.name} {holder.surname}, "
            f"room {holder.room_number}."
        ),
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
    result = start_key_handover(
        DEFAULT_DATABASE_PATH,
        telegram_user_id,
        DEFAULT_KEY_ID,
    )

    if result.status == HandoverStatus.NOT_CURRENT_HOLDER:
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
    result = confirm_key_obtained(
        DEFAULT_DATABASE_PATH,
        telegram_user_id,
        DEFAULT_KEY_ID,
    )

    if result.status == ConfirmKeyStatus.MISSING_TELEGRAM_USER:
        await query.answer("Could not identify you.")
        await reply_with_start_state(
            message,
            "Could not confirm key ownership because Telegram user is missing.",
        )
        return

    if result.status == ConfirmKeyStatus.USER_NOT_REGISTERED:
        await query.answer("You are not registered.")
        await reply_with_start_state(
            message,
            "Could not confirm key ownership because you are not registered.",
            telegram_user_id=telegram_user_id,
        )
        return

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
    """Run the Telegram bot."""
    initialize_database(DEFAULT_DATABASE_PATH)
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .concurrent_updates(True)
        .read_timeout(30)
        .write_timeout(30)
        .build()
    )

    application.add_handler(CommandHandler("start", start_state_command_handler))
    application.add_handler(CallbackQueryHandler(callback_query_handler))
    print("Telegram Bot started!", flush=True)
    application.run_polling()


if __name__ == "__main__":
    main()
