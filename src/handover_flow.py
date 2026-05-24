import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from telegram import CallbackQuery, Message
from src.database import change_key_holder,get_gym_member_id_by_telegram_user_id
from src.bot import reply_holder_key_handover_cancel_button
from src import messages
from src.config import DEFAULT_DATABASE_PATH, DEFAULT_KEY_ID,HANDOVER_WINDOW_SECONDS
from src.keyboards import build_key_obtained_receiver_confirmation_keyboard
from src.key_service import HandoverStatus, user_currently_holds_key
from src.telegram_helpers import (
    get_callback_user_display_name,
    get_callback_user_id,
)

StartStateReply = Callable[[Message, str, int | None], Awaitable[None]]

@dataclass
class PendingHandover:
    holder_user_id: int
    holder_display_name: str
    message: Message
    state_change_function: StartStateReply
    timeout_task: asyncio.Task[None]

PENDING_HANDOVERS: dict[int, PendingHandover] = {}

async def answer_with_function(
    query: CallbackQuery,
    answer_text: str,
    message: Message,
    reply_text: str,
    telegram_user_id: int | None,
    change_state_function: StartStateReply,
) -> None:
    await change_state_function(message, reply_text, telegram_user_id)

def start_pending_handover(key_id,holder_user_id: int,holder_display_name: str,message: Message,state_change_function: StartStateReply) -> None:
    if key_id in PENDING_HANDOVERS:
        raise ValueError(f"handover is already pending for key: {key_id}")

    timeout_task = asyncio.create_task(fail_pending_handover_after_timeout(key_id))
    PENDING_HANDOVERS[key_id] = PendingHandover(
        holder_user_id=holder_user_id,
        holder_display_name=holder_display_name,
        message=message,
        state_change_function=state_change_function,
        timeout_task=timeout_task,
    )

async def fail_pending_handover_after_timeout(key_id: int) -> None:
    await asyncio.sleep(HANDOVER_WINDOW_SECONDS)
    try:
        pending_handover = PENDING_HANDOVERS.pop(key_id)
        await pending_handover.state_change_function(
            pending_handover.message, messages.HANDOVER_FAILED_ANSWER,
            pending_handover.holder_user_id,
        )
    except:
        return #TODO: implement better handling
        # think if it is possible to get timeout when there are no PENDING_HANDOVERS left

def get_pending_handover(key_id) -> PendingHandover | None:
    pending_handover = PENDING_HANDOVERS.get(key_id)
    if pending_handover is None:
        return None
    return pending_handover

async def handle_key_handover(key_id,query: CallbackQuery,message: Message,state_change_function: StartStateReply) -> None:
    telegram_user_id = get_callback_user_id(query)
    if not user_currently_holds_key(DEFAULT_DATABASE_PATH, telegram_user_id, key_id):
        reply = messages.HANDOVER_NOT_ALLOWED_ANSWER
    elif key_id in PENDING_HANDOVERS:
        reply = messages.HANDOVER_ALREADY_PENDING_ANSWER
    else:
        start_pending_handover(
            key_id,
            telegram_user_id,
            get_callback_user_display_name(query),
            message,
            state_change_function
        )
        # If reached this point, everything went successfully
        reply = messages.HANDOVER_READY_ANSWER
        state_change_function = reply_holder_key_handover_cancel_button
    await answer_with_function(
        query,
        reply,
        message,
        reply,
        telegram_user_id,
        state_change_function
    )

async def handle_pending_handover_obtained_backend(key_id,query: CallbackQuery,message: Message,state_change_function: StartStateReply) -> bool:
    pending_handover = PENDING_HANDOVERS.get(key_id)
    telegram_user_id = get_callback_user_id(query)
    reply = None
    if telegram_user_id is None:
        reply = messages.MISSING_TELEGRAM_USER_ANSWER
    elif pending_handover is None:
        reply = messages.HANDOVER_NO_PENDING_ANSWER  
    elif telegram_user_id == pending_handover.holder_user_id:
        reply = messages.HANDOVER_SELF_CONFIRMATION_ANSWER
    if reply is not None:
        await answer_with_function(query, reply, message,reply, telegram_user_id, state_change_function)
    else:
        await query.answer(messages.PLEASE_CONFIRM_KEY_OBTAINED)
        prompt = messages.HANDOVER_CONFIRMATION_PROMPT.format(
            from_member=pending_handover.holder_display_name,
        )
        await message.reply_text(
            prompt,
            reply_markup=build_key_obtained_receiver_confirmation_keyboard(),
        )

async def handle_pending_handover_confirmation(key_id,query: CallbackQuery,message: Message,state_change_function: StartStateReply) -> bool:
    telegram_user_id = get_callback_user_id(query)
    reply = None
    member_id = None
    pending_handover = get_pending_handover(key_id)
    if pending_handover is None:
        reply = messages.HANDOVER_NO_PENDING_ANSWER
    elif telegram_user_id is None:
        reply = messages.MISSING_TELEGRAM_USER_ANSWER
    else:
        if telegram_user_id == pending_handover.holder_user_id:
            reply = messages.HANDOVER_SELF_CONFIRMATION_ANSWER
        else:
            member_id = get_gym_member_id_by_telegram_user_id(DEFAULT_DATABASE_PATH,telegram_user_id)
            if member_id is None:
                reply = messages.UNREGISTERED_USER_ANSWER
    if reply is not None:
        await answer_with_function(
            query, reply, message,reply, telegram_user_id, state_change_function)
    else:
        await complete_handover_interaction(member_id,key_id,query, pending_handover)

async def complete_handover_interaction(
    member_id,
    key_id:int,
    query: CallbackQuery,
    pending_handover: PendingHandover,
) -> None:
    change_key_holder(DEFAULT_DATABASE_PATH,key_id,member_id)
    PENDING_HANDOVERS.pop(key_id)
    pending_handover.timeout_task.cancel()
    handover_text = messages.HANDOVER_COMPLETED_ANSWER.format(
        from_member=pending_handover.holder_display_name,
        to_member=get_callback_user_display_name(query),
    )
    # answered in bot -> await query.answer(messages.HANDOVER_COMPLETED_ANSWER)
    await pending_handover.state_change_function(
        pending_handover.message, handover_text, pending_handover.holder_user_id,
    )
    await pending_handover.state_change_function(
        query.message, handover_text, get_callback_user_id(query)
    )
    

#TODO: implement for handing side
async def handle_pending_handover_cancellation(
    key_id:int,
    query: CallbackQuery,
    message: Message,
    state_change_function: StartStateReply,
) -> None:
    pending_handover = get_pending_handover(key_id)
    PENDING_HANDOVERS.pop(key_id,None)
    pending_handover.timeout_task.cancel()
    reply = messages.KEY_OBTAINED_CANCELLED_ANSWER
    await answer_with_function(
            query, reply, message,reply, None, state_change_function)