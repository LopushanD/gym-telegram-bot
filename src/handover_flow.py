import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from telegram import CallbackQuery, Message

from src import messages
from src.config import DEFAULT_DATABASE_PATH, DEFAULT_KEY_ID
from src.keyboards import build_key_obtained_confirmation_keyboard
from src.key_service import HandoverStatus, start_key_handover
from src.telegram_helpers import (
    get_callback_user_display_name,
    get_callback_user_id,
    messages_are_from_same_chat,
)


StartStateReply = Callable[[Message, str, int | None], Awaitable[None]]
HANDOVER_WINDOW_SECONDS = 30


@dataclass
class PendingHandover:
    holder_user_id: int
    holder_display_name: str
    message: Message
    send_start: StartStateReply
    timeout_task: asyncio.Task[None]


PENDING_HANDOVERS: dict[int, PendingHandover] = {}


async def answer_with_start(
    query: CallbackQuery,
    answer_text: str,
    message: Message,
    reply_text: str,
    telegram_user_id: int | None,
    send_start: StartStateReply,
) -> None:
    await query.answer(answer_text)
    await send_start(message, reply_text, telegram_user_id)


def start_pending_handover(
    holder_user_id: int,
    holder_display_name: str,
    message: Message,
    send_start: StartStateReply,
) -> None:
    if DEFAULT_KEY_ID in PENDING_HANDOVERS:
        raise ValueError(f"handover is already pending for key: {DEFAULT_KEY_ID}")

    timeout_task = asyncio.create_task(fail_pending_handover_after_timeout(DEFAULT_KEY_ID))
    PENDING_HANDOVERS[DEFAULT_KEY_ID] = PendingHandover(
        holder_user_id=holder_user_id,
        holder_display_name=holder_display_name,
        message=message,
        send_start=send_start,
        timeout_task=timeout_task,
    )


async def fail_pending_handover_after_timeout(key_id: int) -> None:
    await asyncio.sleep(HANDOVER_WINDOW_SECONDS)
    pending_handover = PENDING_HANDOVERS.pop(key_id, None)
    if pending_handover is None:
        return

    await pending_handover.send_start(
        pending_handover.message, messages.HANDOVER_FAILED_TEXT,
        pending_handover.holder_user_id,
    )


def complete_pending_handover(new_holder_user_id: int | None) -> PendingHandover | None:
    pending_handover = PENDING_HANDOVERS.get(DEFAULT_KEY_ID)
    if pending_handover is None:
        return None

    if new_holder_user_id == pending_handover.holder_user_id:
        return pending_handover

    PENDING_HANDOVERS.pop(DEFAULT_KEY_ID)
    pending_handover.timeout_task.cancel()
    return pending_handover


def cancel_pending_handover() -> PendingHandover | None:
    pending_handover = PENDING_HANDOVERS.pop(DEFAULT_KEY_ID, None)
    if pending_handover is None:
        return None

    pending_handover.timeout_task.cancel()
    return pending_handover


async def handle_key_handover(
    query: CallbackQuery,
    message: Message,
    send_start: StartStateReply,
) -> None:
    telegram_user_id = get_callback_user_id(query)
    result = start_key_handover(DEFAULT_DATABASE_PATH, telegram_user_id, DEFAULT_KEY_ID)

    if result.status == HandoverStatus.NOT_CURRENT_HOLDER or telegram_user_id is None:
        await answer_with_start(
            query,
            messages.HANDOVER_NOT_ALLOWED_ANSWER,
            message,
            messages.HANDOVER_NOT_ALLOWED_TEXT,
            telegram_user_id,
            send_start,
        )
        return

    if DEFAULT_KEY_ID in PENDING_HANDOVERS:
        await answer_with_start(
            query,
            messages.HANDOVER_ALREADY_PENDING_ANSWER,
            message,
            messages.HANDOVER_ALREADY_PENDING_TEXT,
            telegram_user_id,
            send_start,
        )
        return

    start_pending_handover(
        telegram_user_id,
        get_callback_user_display_name(query),
        message,
        send_start,
    )
    await answer_with_start(
        query,
        messages.HANDOVER_READY_ANSWER,
        message,
        messages.HANDOVER_READY_TEXT,
        telegram_user_id,
        send_start,
    )


async def handle_pending_handover_obtained(
    query: CallbackQuery,
    message: Message,
    send_start: StartStateReply,
) -> bool:
    pending_handover = PENDING_HANDOVERS.get(DEFAULT_KEY_ID)
    if pending_handover is None:
        return False

    telegram_user_id = get_callback_user_id(query)
    if telegram_user_id is None:
        await answer_with_start(
            query, messages.MISSING_TELEGRAM_USER_ANSWER, message, messages.MISSING_TELEGRAM_USER_TEXT,
            None, send_start,
        )
        return True

    if telegram_user_id == pending_handover.holder_user_id:
        await answer_with_start(
            query, messages.HANDOVER_SELF_CONFIRMATION_ANSWER, message,
            messages.HANDOVER_SELF_CONFIRMATION_TEXT, telegram_user_id, send_start,
        )
        return True

    await query.answer(messages.PLEASE_CONFIRM_KEY_OBTAINED)
    prompt = messages.HANDOVER_CONFIRMATION_PROMPT.format(
        from_member=pending_handover.holder_display_name,
    )
    await message.reply_text(
        prompt,
        reply_markup=build_key_obtained_confirmation_keyboard(),
    )
    return True


async def handle_pending_handover_confirmation(
    query: CallbackQuery,
    message: Message,
    send_start: StartStateReply,
) -> bool:
    telegram_user_id = get_callback_user_id(query)
    if telegram_user_id is None:
        if DEFAULT_KEY_ID not in PENDING_HANDOVERS:
            return False
        await answer_with_start(
            query, messages.MISSING_TELEGRAM_USER_ANSWER, message, messages.MISSING_TELEGRAM_USER_TEXT,
            None, send_start,
        )
        return True

    pending_handover = complete_pending_handover(telegram_user_id)
    if pending_handover is None:
        return False

    if telegram_user_id == pending_handover.holder_user_id:
        await answer_with_start(
            query, messages.HANDOVER_SELF_CONFIRMATION_ANSWER, message,
            messages.HANDOVER_SELF_CONFIRMATION_TEXT, telegram_user_id, send_start,
        )
        return True

    await complete_handover_interaction(
        query, message, telegram_user_id, pending_handover, send_start,
    )
    return True


async def complete_handover_interaction(
    query: CallbackQuery,
    message: Message,
    new_holder_user_id: int,
    pending_handover: PendingHandover,
    send_start: StartStateReply,
) -> None:
    handover_text = messages.HANDOVER_COMPLETED_TEXT.format(
        from_member=pending_handover.holder_display_name,
        to_member=get_callback_user_display_name(query),
    )
    await query.answer(messages.HANDOVER_COMPLETED_ANSWER)
    await pending_handover.send_start(
        pending_handover.message, handover_text, pending_handover.holder_user_id,
    )
    if messages_are_from_same_chat(pending_handover.message, message):
        return

    await send_start(message, handover_text, new_holder_user_id)


async def handle_pending_handover_cancellation(
    query: CallbackQuery,
    message: Message,
    send_start: StartStateReply,
) -> bool:
    pending_handover = cancel_pending_handover()
    if pending_handover is None:
        return False

    await query.answer(messages.KEY_OBTAINED_CANCELLED_ANSWER)
    await notify_handover_cancelled(
        pending_handover, message, get_callback_user_id(query), send_start,
    )
    return True


async def notify_handover_cancelled(
    pending_handover: PendingHandover,
    cancellation_message: Message,
    cancelling_user_id: int | None,
    send_start: StartStateReply,
) -> None:
    await pending_handover.send_start(
        pending_handover.message, messages.HANDOVER_FAILED_TEXT,
        pending_handover.holder_user_id,
    )
    if messages_are_from_same_chat(pending_handover.message, cancellation_message):
        return

    await send_start(
        cancellation_message, messages.KEY_OBTAINED_CANCELLED_TEXT, cancelling_user_id,
    )
