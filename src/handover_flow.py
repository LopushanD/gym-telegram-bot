import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from telegram import CallbackQuery, Message

from src.config import DEFAULT_DATABASE_PATH, DEFAULT_KEY_ID
from src.keyboards import build_key_obtained_confirmation_keyboard
from src.key_service import HandoverStatus, start_key_handover
from src.messages import (
    HANDOVER_ALREADY_PENDING_ANSWER,
    HANDOVER_ALREADY_PENDING_TEXT,
    HANDOVER_CONFIRMATION_PROMPT,
    HANDOVER_COMPLETED_ANSWER,
    HANDOVER_COMPLETED_TEXT,
    HANDOVER_FAILED_TEXT,
    HANDOVER_NOT_ALLOWED_ANSWER,
    HANDOVER_NOT_ALLOWED_TEXT,
    HANDOVER_READY_ANSWER,
    HANDOVER_READY_TEXT,
    HANDOVER_SELF_CONFIRMATION_ANSWER,
    HANDOVER_SELF_CONFIRMATION_TEXT,
    KEY_OBTAINED_CANCELLED_ANSWER,
    KEY_OBTAINED_CANCELLED_TEXT,
    MISSING_TELEGRAM_USER_ANSWER,
    MISSING_TELEGRAM_USER_TEXT,
    PLEASE_CONFIRM_KEY_OBTAINED,
)
from src.telegram_helpers import (
    get_callback_user_display_name,
    get_callback_user_id,
    messages_are_from_same_chat,
)


StartStateReply = Callable[[Message, str, int | None], Awaitable[None]]
HANDOVER_WINDOW_SECONDS = 30


@dataclass
class PendingHandover:
    key_id: int
    holder_user_id: int
    holder_display_name: str
    message: Message
    reply_with_start_state: StartStateReply
    timeout_task: asyncio.Task[None]


PENDING_HANDOVERS: dict[int, PendingHandover] = {}


def has_pending_handover(key_id: int = DEFAULT_KEY_ID) -> bool:
    return key_id in PENDING_HANDOVERS


def start_pending_handover(
    key_id: int,
    holder_user_id: int,
    holder_display_name: str,
    message: Message,
    reply_with_start_state: StartStateReply,
) -> None:
    if key_id in PENDING_HANDOVERS:
        raise ValueError(f"handover is already pending for key: {key_id}")

    timeout_task = asyncio.create_task(fail_pending_handover_after_timeout(key_id))
    PENDING_HANDOVERS[key_id] = PendingHandover(
        key_id=key_id,
        holder_user_id=holder_user_id,
        holder_display_name=holder_display_name,
        message=message,
        reply_with_start_state=reply_with_start_state,
        timeout_task=timeout_task,
    )


async def fail_pending_handover_after_timeout(key_id: int) -> None:
    await asyncio.sleep(HANDOVER_WINDOW_SECONDS)
    pending_handover = PENDING_HANDOVERS.pop(key_id, None)
    if pending_handover is None:
        return

    await pending_handover.reply_with_start_state(
        pending_handover.message,
        HANDOVER_FAILED_TEXT,
        pending_handover.holder_user_id,
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


async def handle_key_handover(
    query: CallbackQuery,
    message: Message,
    reply_with_start_state: StartStateReply,
) -> None:
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
            telegram_user_id,
        )
        return

    if telegram_user_id is None:
        await query.answer(HANDOVER_NOT_ALLOWED_ANSWER)
        await reply_with_start_state(
            message,
            HANDOVER_NOT_ALLOWED_TEXT,
            telegram_user_id,
        )
        return

    if has_pending_handover(DEFAULT_KEY_ID):
        await query.answer(HANDOVER_ALREADY_PENDING_ANSWER)
        await reply_with_start_state(
            message,
            HANDOVER_ALREADY_PENDING_TEXT,
            telegram_user_id,
        )
        return

    start_pending_handover(
        DEFAULT_KEY_ID,
        telegram_user_id,
        get_callback_user_display_name(query),
        message,
        reply_with_start_state,
    )
    await query.answer(HANDOVER_READY_ANSWER)
    await reply_with_start_state(
        message,
        HANDOVER_READY_TEXT,
        telegram_user_id,
    )


async def handle_pending_handover_obtained(
    query: CallbackQuery,
    message: Message,
    reply_with_start_state: StartStateReply,
) -> bool:
    if not has_pending_handover(DEFAULT_KEY_ID):
        return False

    telegram_user_id = get_callback_user_id(query)
    if telegram_user_id is None:
        await query.answer(MISSING_TELEGRAM_USER_ANSWER)
        await reply_with_start_state(
            message,
            MISSING_TELEGRAM_USER_TEXT,
            telegram_user_id,
        )
        return True

    pending_handover = PENDING_HANDOVERS.get(DEFAULT_KEY_ID)
    if pending_handover is None:
        return False

    if telegram_user_id == pending_handover.holder_user_id:
        await query.answer(HANDOVER_SELF_CONFIRMATION_ANSWER)
        await reply_with_start_state(
            message,
            HANDOVER_SELF_CONFIRMATION_TEXT,
            telegram_user_id,
        )
        return True

    await query.answer(PLEASE_CONFIRM_KEY_OBTAINED)
    await message.reply_text(
        HANDOVER_CONFIRMATION_PROMPT.format(
            from_member=pending_handover.holder_display_name,
        ),
        reply_markup=build_key_obtained_confirmation_keyboard(),
    )
    return True


async def handle_pending_handover_confirmation(
    query: CallbackQuery,
    message: Message,
    reply_with_start_state: StartStateReply,
) -> bool:
    if not has_pending_handover(DEFAULT_KEY_ID):
        return False

    telegram_user_id = get_callback_user_id(query)
    if telegram_user_id is None:
        await query.answer(MISSING_TELEGRAM_USER_ANSWER)
        await reply_with_start_state(
            message,
            MISSING_TELEGRAM_USER_TEXT,
            telegram_user_id,
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
            telegram_user_id,
        )
        return True

    new_holder_display_name = get_callback_user_display_name(query)
    handover_text = HANDOVER_COMPLETED_TEXT.format(
        from_member=pending_handover.holder_display_name,
        to_member=new_holder_display_name,
    )
    await query.answer(HANDOVER_COMPLETED_ANSWER)
    await pending_handover.reply_with_start_state(
        pending_handover.message,
        handover_text,
        pending_handover.holder_user_id,
    )
    if messages_are_from_same_chat(pending_handover.message, message):
        return True

    await reply_with_start_state(
        message,
        handover_text,
        telegram_user_id,
    )
    return True


async def handle_pending_handover_cancellation(
    query: CallbackQuery,
    message: Message,
    reply_with_start_state: StartStateReply,
) -> bool:
    pending_handover = cancel_pending_handover(DEFAULT_KEY_ID)
    if pending_handover is None:
        return False

    await query.answer(KEY_OBTAINED_CANCELLED_ANSWER)
    await pending_handover.reply_with_start_state(
        pending_handover.message,
        HANDOVER_FAILED_TEXT,
        pending_handover.holder_user_id,
    )
    if messages_are_from_same_chat(pending_handover.message, message):
        return True

    await reply_with_start_state(
        message,
        KEY_OBTAINED_CANCELLED_TEXT,
        get_callback_user_id(query),
    )
    return True
