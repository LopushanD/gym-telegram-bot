import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
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
from src.key_service import (
    ConfirmKeyStatus,
    HandoverStatus,
    confirm_key_obtained,
    get_key_holder,
    start_key_handover,
    user_currently_holds_key,
)
from src.messages import (
    HANDOVER_NOT_ALLOWED_ANSWER,
    HANDOVER_NOT_ALLOWED_TEXT,
    HANDOVER_ALREADY_PENDING_ANSWER,
    HANDOVER_ALREADY_PENDING_TEXT,
    HANDOVER_CONFIRMATION_PROMPT,
    HANDOVER_COMPLETED_ANSWER,
    HANDOVER_COMPLETED_TEXT,
    HANDOVER_FAILED_TEXT,
    HANDOVER_READY_ANSWER,
    HANDOVER_READY_TEXT,
    HANDOVER_SELF_CONFIRMATION_ANSWER,
    HANDOVER_SELF_CONFIRMATION_TEXT,
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


CallbackHandler = Callable[[CallbackQuery, Message], Awaitable[None]]
HANDOVER_WINDOW_SECONDS = 30


@dataclass
class PendingHandover:
    key_id: int
    holder_user_id: int
    holder_display_name: str
    message: Message
    timeout_task: asyncio.Task[None]


PENDING_HANDOVERS: dict[int, PendingHandover] = {}


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


def get_callback_user_display_name(query: CallbackQuery) -> str:
    user = getattr(query, "from_user", None)
    if user is None:
        return "Unknown member"

    full_name = getattr(user, "full_name", None)
    if full_name:
        return full_name

    username = getattr(user, "username", None)
    if username:
        return f"@{username}"

    user_id = getattr(user, "id", None)
    if user_id is not None:
        return f"member {user_id}"

    return "Unknown member"


def get_message_chat_id(message: Message) -> int | None:
    chat_id = getattr(message, "chat_id", None)
    if chat_id is not None:
        return chat_id

    chat = getattr(message, "chat", None)
    return getattr(chat, "id", None)


def messages_are_from_same_chat(first_message: Message, second_message: Message) -> bool:
    first_chat_id = get_message_chat_id(first_message)
    second_chat_id = get_message_chat_id(second_message)

    return first_chat_id is not None and first_chat_id == second_chat_id


def has_pending_handover(key_id: int = DEFAULT_KEY_ID) -> bool:
    return key_id in PENDING_HANDOVERS


def start_pending_handover(
    key_id: int,
    holder_user_id: int,
    holder_display_name: str,
    message: Message,
) -> None:
    if key_id in PENDING_HANDOVERS:
        raise ValueError(f"handover is already pending for key: {key_id}")

    timeout_task = asyncio.create_task(fail_pending_handover_after_timeout(key_id))
    PENDING_HANDOVERS[key_id] = PendingHandover(
        key_id=key_id,
        holder_user_id=holder_user_id,
        holder_display_name=holder_display_name,
        message=message,
        timeout_task=timeout_task,
    )


async def fail_pending_handover_after_timeout(key_id: int) -> None:
    await asyncio.sleep(HANDOVER_WINDOW_SECONDS)
    pending_handover = PENDING_HANDOVERS.pop(key_id, None)
    if pending_handover is None:
        return

    await reply_with_start_state(
        pending_handover.message,
        HANDOVER_FAILED_TEXT,
        telegram_user_id=pending_handover.holder_user_id,
    )


def complete_pending_handover(
    key_id: int,
    new_holder_user_id: int | None,
) -> PendingHandover | None:
    pending_handover = PENDING_HANDOVERS.get(key_id)
    if pending_handover is None:
        return None

    if new_holder_user_id == pending_handover.holder_user_id:
        return pending_handover

    PENDING_HANDOVERS.pop(key_id)
    pending_handover.timeout_task.cancel()
    return pending_handover


def cancel_pending_handover(key_id: int) -> PendingHandover | None:
    pending_handover = PENDING_HANDOVERS.pop(key_id, None)
    if pending_handover is None:
        return None

    pending_handover.timeout_task.cancel()
    return pending_handover


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
    if has_pending_handover(DEFAULT_KEY_ID):
        await handle_pending_handover_obtained(query, message)
        return

    await query.answer(PLEASE_CONFIRM_KEY_OBTAINED)
    await message.reply_text(
        KEY_OBTAINED_CONFIRMATION_PROMPT,
        reply_markup=build_key_obtained_confirmation_keyboard(),
    )


async def handle_pending_handover_obtained(
    query: CallbackQuery,
    message: Message,
) -> None:
    telegram_user_id = get_callback_user_id(query)
    if telegram_user_id is None:
        await query.answer(MISSING_TELEGRAM_USER_ANSWER)
        await reply_with_start_state(
            message,
            MISSING_TELEGRAM_USER_TEXT,
        )
        return

    pending_handover = PENDING_HANDOVERS.get(DEFAULT_KEY_ID)
    if pending_handover is None:
        await query.answer(PLEASE_CONFIRM_KEY_OBTAINED)
        await message.reply_text(
            KEY_OBTAINED_CONFIRMATION_PROMPT,
            reply_markup=build_key_obtained_confirmation_keyboard(),
        )
        return

    if telegram_user_id == pending_handover.holder_user_id:
        await query.answer(HANDOVER_SELF_CONFIRMATION_ANSWER)
        await reply_with_start_state(
            message,
            HANDOVER_SELF_CONFIRMATION_TEXT,
            telegram_user_id=telegram_user_id,
        )
        return

    await query.answer(PLEASE_CONFIRM_KEY_OBTAINED)
    await message.reply_text(
        HANDOVER_CONFIRMATION_PROMPT.format(
            from_member=pending_handover.holder_display_name,
        ),
        reply_markup=build_key_obtained_confirmation_keyboard(),
    )


async def handle_pending_handover_confirmation(
    query: CallbackQuery,
    message: Message,
) -> bool:
    if not has_pending_handover(DEFAULT_KEY_ID):
        return False

    telegram_user_id = get_callback_user_id(query)
    if telegram_user_id is None:
        await query.answer(MISSING_TELEGRAM_USER_ANSWER)
        await reply_with_start_state(
            message,
            MISSING_TELEGRAM_USER_TEXT,
        )
        return True

    pending_handover = complete_pending_handover(DEFAULT_KEY_ID, telegram_user_id)
    if pending_handover is None:
        return False

    if telegram_user_id == pending_handover.holder_user_id:
        await query.answer(HANDOVER_SELF_CONFIRMATION_ANSWER)
        await reply_with_start_state(
            message,
            HANDOVER_SELF_CONFIRMATION_TEXT,
            telegram_user_id=telegram_user_id,
        )
        return True

    new_holder_display_name = get_callback_user_display_name(query)
    handover_text = HANDOVER_COMPLETED_TEXT.format(
        from_member=pending_handover.holder_display_name,
        to_member=new_holder_display_name,
    )
    await query.answer(HANDOVER_COMPLETED_ANSWER)
    await reply_with_start_state(
        pending_handover.message,
        handover_text,
        telegram_user_id=pending_handover.holder_user_id,
    )
    if messages_are_from_same_chat(pending_handover.message, message):
        return True

    await reply_with_start_state(
        message,
        handover_text,
        telegram_user_id=telegram_user_id,
    )
    return True


async def handle_key_handover(query: CallbackQuery, message: Message) -> None:
    telegram_user_id = get_callback_user_id(query)
    result = start_key_handover(
        DEFAULT_DATABASE_PATH,
        telegram_user_id,
        DEFAULT_KEY_ID,
    )

    if result.status == HandoverStatus.NOT_CURRENT_HOLDER:
        await query.answer(HANDOVER_NOT_ALLOWED_ANSWER)
        await reply_with_start_state(
            message,
            HANDOVER_NOT_ALLOWED_TEXT,
            telegram_user_id=telegram_user_id,
        )
        return

    if telegram_user_id is None:
        await query.answer(HANDOVER_NOT_ALLOWED_ANSWER)
        await reply_with_start_state(
            message,
            HANDOVER_NOT_ALLOWED_TEXT,
            telegram_user_id=telegram_user_id,
        )
        return

    if has_pending_handover(DEFAULT_KEY_ID):
        await query.answer(HANDOVER_ALREADY_PENDING_ANSWER)
        await reply_with_start_state(
            message,
            HANDOVER_ALREADY_PENDING_TEXT,
            telegram_user_id=telegram_user_id,
        )
        return

    start_pending_handover(
        DEFAULT_KEY_ID,
        telegram_user_id,
        get_callback_user_display_name(query),
        message,
    )
    await query.answer(HANDOVER_READY_ANSWER)
    await reply_with_start_state(
        message,
        HANDOVER_READY_TEXT,
        telegram_user_id=telegram_user_id,
    )


async def handle_key_obtained_confirmation(
    query: CallbackQuery,
    message: Message,
) -> None:
    if await handle_pending_handover_confirmation(query, message):
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
    if await handle_pending_handover_cancellation(query, message):
        return

    await query.answer(KEY_OBTAINED_CANCELLED_ANSWER)
    await reply_with_start_state(
        message,
        KEY_OBTAINED_CANCELLED_TEXT,
        telegram_user_id=get_callback_user_id(query),
    )


async def handle_pending_handover_cancellation(
    query: CallbackQuery,
    message: Message,
) -> bool:
    pending_handover = cancel_pending_handover(DEFAULT_KEY_ID)
    if pending_handover is None:
        return False

    await query.answer(KEY_OBTAINED_CANCELLED_ANSWER)
    await reply_with_start_state(
        pending_handover.message,
        HANDOVER_FAILED_TEXT,
        telegram_user_id=pending_handover.holder_user_id,
    )
    if messages_are_from_same_chat(pending_handover.message, message):
        return True

    await reply_with_start_state(
        message,
        KEY_OBTAINED_CANCELLED_TEXT,
        telegram_user_id=get_callback_user_id(query),
    )
    return True


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
