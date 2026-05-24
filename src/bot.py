from collections.abc import Awaitable, Callable
from typing import cast

from telegram import CallbackQuery, Message, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler

from src import messages
from src.bot_replies import (
    edit_to_start_state,
    reply_with_start_state,
)
from src.keyboards import (
    HOLDER_KEY_HANDOVER_CALLBACK,
    HOLDER_KEY_HANDOVER_CANCEL_CALLBACK,
    HOLDER_KEY_RETURN_MAILBOX_CALLBACK,
    HOLDER_KEY_RETURN_MAILBOX_CANCEL_CALLBACK,
    HOLDER_KEY_RETURN_MAILBOX_CONFIRM_CALLBACK,
    KEY_HANDOVER_RECEIVER_CONFIRMATION_CALLBACK,
    RECEIVER_HANDOVER_KEY_OBTAINED_CALLBACK,
    RECEIVER_KEY_INFO_CALLBACK,
    RECEIVER_KEY_HANDOVER_CANCEL_CALLBACK,
    RECEIVER_MAILBOX_KEY_OBTAINED_CALLBACK,
    build_key_return_mailbox_confirmation_keyboard,
)
from src.config import BOT_TOKEN, DEFAULT_DATABASE_PATH, DEFAULT_KEY_ID,MAILBOX_MEMBER_ID
from src.database import initialize_database
from src.handover_flow import (
    handle_key_handover,
    handle_pending_handover_confirmation,
    handle_pending_handover_obtained_backend,
    handle_pending_handover_cancellation,
)
from src.key_service import (
    get_key_holder,
    ReturnToMailboxStatus,
    return_key_to_mailbox,
    TakeFromMailboxStatus,
    take_key_from_mailbox,
)
from src.messages import (
    UNKNOWN_CALLBACK_ANSWER,
    KEY_OBTAINED_CANCELLED_ANSWER,
    current_key_holder_text,
)
from src.telegram_helpers import get_callback_user_id, get_update_user_id

CallbackHandler = Callable[[CallbackQuery, Message], Awaitable[None]]


async def start_state_command_handler(update: Update, context) -> None:
    await reply_with_start_state(
        update.effective_message,
        messages.START_STATE_TEXT,
        telegram_user_id=get_update_user_id(update),
    )


async def callback_query_handler(update: Update,context) -> None:
    query = update.callback_query
    received_message = cast(Message, query.message)

    callback_data = query.data if isinstance(query.data, str) else None
    handler = CALLBACK_HANDLERS.get(callback_data, handle_unknown_callback)
    await handler(query, received_message)

async def handle_key_request(query: CallbackQuery, message: Message) -> None:
    holder = get_key_holder(DEFAULT_DATABASE_PATH, key_id=DEFAULT_KEY_ID)
    if holder is None:
        text = messages.START_STATE_TEXT
    else:
        text = current_key_holder_text(holder)
    await edit_to_start_state(
        message,
        text,
        telegram_user_id=get_callback_user_id(query),
    )

async def handle_key_obtained(query: CallbackQuery, message: Message) -> None:
    await query.answer()
    await handle_pending_handover_obtained_backend(DEFAULT_KEY_ID,query,message,edit_to_start_state)

async def handle_key_handover_callback(query: CallbackQuery,message: Message) -> None:
    await query.answer()
    await handle_key_handover(DEFAULT_KEY_ID, query, message, edit_to_start_state)

async def handle_key_obtained_confirmation(query: CallbackQuery,message: Message) -> None:
    await query.answer()
    await handle_pending_handover_confirmation(DEFAULT_KEY_ID,query,message,edit_to_start_state)

async def handle_key_obtained_cancellation(query: CallbackQuery,message: Message) -> None:
    await query.answer()
    await edit_to_start_state(query.message,messages.START_STATE_TEXT,query.from_user.id)

async def handle_unknown_callback(query: CallbackQuery, message: Message) -> None:
    await query.answer()
    await edit_to_start_state(message,UNKNOWN_CALLBACK_ANSWER,
                                 telegram_user_id=get_callback_user_id(query)
    )
    
async def handle_holder_key_handover_cancellation(query: CallbackQuery, message: Message):
  await query.answer()
  await handle_pending_handover_cancellation(DEFAULT_KEY_ID,query,message)

async def handle_key_return_mailbox(query: CallbackQuery, message: Message) -> None:
    await query.answer(messages.PLEASE_CONFIRM_KEY_OBTAINED)
    await message.edit_text(
        messages.KEY_RETURN_MAILBOX_CONFIRMATION_PROMPT,
        reply_markup=build_key_return_mailbox_confirmation_keyboard())

async def handle_key_return_mailbox_confirmation(query: CallbackQuery,message: Message) -> None:
    telegram_user_id = get_callback_user_id(query)
    result = return_key_to_mailbox(DEFAULT_DATABASE_PATH, telegram_user_id, DEFAULT_KEY_ID)
    if result.status == ReturnToMailboxStatus.RETURNED:
        reply = messages.KEY_RETURNED_TO_MAILBOX_ANSWER
    else:
        reply = messages.KEY_RETURN_MAILBOX_NOT_ALLOWED_ANSWER
    await query.answer()
    await edit_to_start_state(message,reply,telegram_user_id)

async def handle_key_return_mailbox_cancellation(query: CallbackQuery,message: Message) -> None:
    await query.answer(messages.KEY_RETURN_MAILBOX_CANCELLED_ANSWER)
    await edit_to_start_state(message,messages.KEY_RETURN_MAILBOX_CANCELLED_ANSWER,
        get_callback_user_id(query))

async def handle_key_obtained_from_mailbox(query: CallbackQuery,message: Message) -> None:
    telegram_user_id = get_callback_user_id(query)
    result = take_key_from_mailbox(DEFAULT_DATABASE_PATH,telegram_user_id,DEFAULT_KEY_ID,MAILBOX_MEMBER_ID)
    if result.status == TakeFromMailboxStatus.TAKEN:
        reply = messages.KEY_TAKEN_FROM_MAILBOX_ANSWER
    elif result.status == TakeFromMailboxStatus.KEY_NOT_IN_MAILBOX:
        reply = messages.KEY_NOT_IN_MAILBOX_ANSWER
    else:
        reply = messages.UNREGISTERED_USER_ANSWER
    await query.answer()
    await edit_to_start_state(message, reply, telegram_user_id)

CALLBACK_HANDLERS: dict[str, CallbackHandler] = {
    RECEIVER_KEY_INFO_CALLBACK: handle_key_request,
    RECEIVER_HANDOVER_KEY_OBTAINED_CALLBACK: handle_key_obtained,
    RECEIVER_MAILBOX_KEY_OBTAINED_CALLBACK: handle_key_obtained_from_mailbox,
    HOLDER_KEY_HANDOVER_CALLBACK: handle_key_handover_callback,
    KEY_HANDOVER_RECEIVER_CONFIRMATION_CALLBACK: handle_key_obtained_confirmation,
    RECEIVER_KEY_HANDOVER_CANCEL_CALLBACK: handle_key_obtained_cancellation,
    HOLDER_KEY_HANDOVER_CANCEL_CALLBACK: handle_holder_key_handover_cancellation,
    HOLDER_KEY_RETURN_MAILBOX_CALLBACK: handle_key_return_mailbox,
    HOLDER_KEY_RETURN_MAILBOX_CONFIRM_CALLBACK: handle_key_return_mailbox_confirmation,
    HOLDER_KEY_RETURN_MAILBOX_CANCEL_CALLBACK: handle_key_return_mailbox_cancellation,
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
