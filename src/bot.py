from collections.abc import Awaitable, Callable
from pathlib import Path
import sys
from typing import cast

from telegram import CallbackQuery, Message, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

# Let IDEs run this file directly while keeping package imports everywhere else.
if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.keyboards import (
    CANCEL_KEY_OBTAINED_CALLBACK,
    CONFIRM_KEY_OBTAINED_CALLBACK,
    KEY_HANDOVER_CALLBACK,
    KEY_OBTAINED_CALLBACK,
    KEY_REQUEST_CALLBACK,
    build_key_obtained_confirmation_keyboard,
    build_start_keyboard,
)
from src.config import BOT_TOKEN, DEFAULT_DATABASE_PATH, DEFAULT_KEY_ID
from src.database import initialize_database
from src.handover_flow import (
    handle_key_handover,
    handle_pending_handover_cancellation,
    handle_pending_handover_confirmation,
    handle_pending_handover_obtained,
)
from src.key_service import (
    ConfirmKeyStatus,
    confirm_key_obtained,
    get_key_holder,
    user_currently_holds_key,
)
from src.messages import (
    KEY_OBTAINED_CANCELLED_ANSWER,
    KEY_OBTAINED_CANCELLED_TEXT,
    KEY_OBTAINED_CONFIRMATION_PROMPT,
    KEY_OBTAINED_CONFIRMED_ANSWER,
    KEY_OBTAINED_CONFIRMED_TEXT,
    LOOKING_UP_KEY_HOLDER,
    MISSING_TELEGRAM_USER_ANSWER,
    MISSING_TELEGRAM_USER_TEXT,
    NO_KEY_REGISTERED,
    PLEASE_CONFIRM_KEY_OBTAINED,
    START_STATE_TEXT,
    UNKNOWN_CALLBACK_ANSWER,
    UNKNOWN_CALLBACK_TEXT,
    UNREGISTERED_USER_ANSWER,
    UNREGISTERED_USER_TEXT,
    current_key_holder_text,
)
from src.telegram_helpers import get_callback_user_id, get_update_user_id


CallbackHandler = Callable[[CallbackQuery, Message], Awaitable[None]]


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

    await query.answer(LOOKING_UP_KEY_HOLDER)
    if holder is None:
        await reply_with_start_state(
            message,
            NO_KEY_REGISTERED,
            telegram_user_id=get_callback_user_id(query),
        )
        return

    await reply_with_start_state(
        message,
        current_key_holder_text(holder),
        telegram_user_id=get_callback_user_id(query),
    )


async def handle_key_obtained(query: CallbackQuery, message: Message) -> None:
    if await handle_pending_handover_obtained(
        query,
        message,
        reply_with_start_state,
    ):
        return

    await query.answer(PLEASE_CONFIRM_KEY_OBTAINED)
    await message.reply_text(
        KEY_OBTAINED_CONFIRMATION_PROMPT,
        reply_markup=build_key_obtained_confirmation_keyboard(),
    )


async def handle_key_handover_callback(
    query: CallbackQuery,
    message: Message,
) -> None:
    await handle_key_handover(query, message, reply_with_start_state)


async def handle_key_obtained_confirmation(
    query: CallbackQuery,
    message: Message,
) -> None:
    if await handle_pending_handover_confirmation(
        query,
        message,
        reply_with_start_state,
    ):
        return

    telegram_user_id = get_callback_user_id(query)
    result = confirm_key_obtained(
        DEFAULT_DATABASE_PATH,
        telegram_user_id,
        DEFAULT_KEY_ID,
    )

    if result.status == ConfirmKeyStatus.MISSING_TELEGRAM_USER:
        await query.answer(MISSING_TELEGRAM_USER_ANSWER)
        await reply_with_start_state(
            message,
            MISSING_TELEGRAM_USER_TEXT,
        )
        return

    if result.status == ConfirmKeyStatus.USER_NOT_REGISTERED:
        await query.answer(UNREGISTERED_USER_ANSWER)
        await reply_with_start_state(
            message,
            UNREGISTERED_USER_TEXT,
            telegram_user_id=telegram_user_id,
        )
        return

    await query.answer(KEY_OBTAINED_CONFIRMED_ANSWER)
    await reply_with_start_state(
        message,
        KEY_OBTAINED_CONFIRMED_TEXT,
        telegram_user_id=telegram_user_id,
    )


async def handle_key_obtained_cancellation(
    query: CallbackQuery,
    message: Message,
) -> None:
    if await handle_pending_handover_cancellation(
        query,
        message,
        reply_with_start_state,
    ):
        return

    await query.answer(KEY_OBTAINED_CANCELLED_ANSWER)
    await reply_with_start_state(
        message,
        KEY_OBTAINED_CANCELLED_TEXT,
        telegram_user_id=get_callback_user_id(query),
    )


async def handle_unknown_callback(query: CallbackQuery, message: Message) -> None:
    await query.answer(UNKNOWN_CALLBACK_ANSWER)
    await reply_with_start_state(
        message,
        UNKNOWN_CALLBACK_TEXT,
        telegram_user_id=get_callback_user_id(query),
    )


CALLBACK_HANDLERS: dict[str, CallbackHandler] = {
    KEY_REQUEST_CALLBACK: handle_key_request,
    KEY_OBTAINED_CALLBACK: handle_key_obtained,
    KEY_HANDOVER_CALLBACK: handle_key_handover_callback,
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
