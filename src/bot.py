from collections.abc import Awaitable, Callable
from typing import cast

from telegram import CallbackQuery, Message, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler

from src import messages
from src.admin_commands import (
    activate_key_command_handler,
    add_user_command_handler,
    deactivate_key_command_handler,
    give_key_command_handler,
    help_command_handler,
    key_history_command_handler,
    key_status_command_handler,
    update_user_command_handler,
    users_command_handler,
)
from src.bot_replies import (
    edit_to_start_state,
    reply_with_start_state,
)
from src.keyboards import (
    HOLDER_KEY_HANDOVER_CALLBACK,
    HOLDER_KEY_HANDOVER_CANCEL_CALLBACK,
    
    HOLDER_KEY_RETURN_MAILBOX_CALLBACK,
    HOLDER_KEY_RETURN_MAILBOX_CANCEL_CALLBACK,
    HOLDER_KEY_RETURN_MAILBOX_CONFIRM_CALLBACK_PREFIX,
    HOLDER_KEY_RETURN_MAILBOX_KEY_CHOICE_CALLBACK_PREFIX,
    
    RECEIVER_KEY_HANDOVER_CONFIRM_CALLBACK,
    RECEIVER_HANDOVER_KEY_OBTAINED_CALLBACK,
    RECEIVER_HANDOVER_KEY_CHOICE_CALLBACK_PREFIX,
    RECEIVER_KEY_INFO_CALLBACK,
    RECEIVER_KEY_HANDOVER_CANCEL_CALLBACK,
    
    RECEIVER_MAILBOX_KEY_OBTAINED_CANCEL_CALLBACK,
    RECEIVER_MAILBOX_KEY_OBTAINED_CALLBACK,
    RECEIVER_MAILBOX_KEY_OBTAINED_CONFIRM_CALLBACK_PREFIX,
    RECEIVER_MAILBOX_KEY_CHOICE_CALLBACK_PREFIX,
    build_key_obtained_receiver_key_choice_keyboard,
    build_key_obtained_mailbox_key_choice_keyboard,
    build_key_obtained_mailbox_confirmation_keyboard,
    build_key_return_mailbox_returned_keyboard,
    build_key_return_mailbox_confirmation_keyboard,
    callback_matches_prefix,
    parse_key_id_callback,
)
from src.config import BOT_TOKEN, DEFAULT_DATABASE_PATH
from src.database import initialize_database,get_key_owner_mailbox_info,get_key_id_by_telegram_user_id
from src.handover_flow import (
    handle_key_handover,
    handle_pending_handover_confirmation,
    handle_pending_handover_obtained_backend,
    handle_pending_handover_cancellation,
)
from src.key_service import (
    get_keyholders,
    get_key_count,
    get_key_return_instruction,
    ReturnToMailboxStatus,
    return_key_to_mailbox,
    TakeFromMailboxStatus,
    take_key_from_mailbox,
)
from src.telegram_helpers import get_callback_telegram_user_id, get_update_telegram_user_id
from src.user_commands import clear_command_handler, my_telegram_id_command_handler

CallbackHandler = Callable[[CallbackQuery, Message], Awaitable[None]]


async def start_state_command_handler(update: Update, context) -> None:
    await reply_with_start_state(
        update.effective_message,
        messages.START_USER_MENU_TEXT,
        telegram_user_id=get_update_telegram_user_id(update),
    )


async def callback_query_handler(update: Update,context) -> None:
    query = update.callback_query
    received_message = cast(Message, query.message)

    callback_data = query.data if isinstance(query.data, str) else None
    #TODO Reengineer the way handlers are stored.
    if callback_matches_prefix(
        callback_data,
        RECEIVER_MAILBOX_KEY_CHOICE_CALLBACK_PREFIX
        ):
        await handle_key_obtained_from_mailbox_choice(query,received_message)
    elif callback_matches_prefix(
        callback_data,
        RECEIVER_MAILBOX_KEY_OBTAINED_CONFIRM_CALLBACK_PREFIX,
    ):
        await handle_key_obtained_from_mailbox_confirmation(query, received_message)
    elif callback_matches_prefix(
        callback_data,
        HOLDER_KEY_RETURN_MAILBOX_KEY_CHOICE_CALLBACK_PREFIX,
    ):
        await handle_key_return_mailbox_choice(query, received_message)
    elif callback_matches_prefix(
        callback_data,
        HOLDER_KEY_RETURN_MAILBOX_CONFIRM_CALLBACK_PREFIX,
    ):
        await handle_key_return_mailbox_confirmation(query, received_message)
    elif callback_matches_prefix(
        callback_data,
        RECEIVER_HANDOVER_KEY_CHOICE_CALLBACK_PREFIX
        ):
        await handle_key_obtained_choice(query, received_message)
    elif callback_matches_prefix(
        callback_data,
        RECEIVER_KEY_HANDOVER_CONFIRM_CALLBACK
        ):
        await handle_key_obtained_confirmation(query, received_message)
    else:
        handler = CALLBACK_HANDLERS.get(callback_data, handle_unknown_callback)
        await handler(query, received_message)

async def handle_key_request(query: CallbackQuery, message: Message) -> None:
    keyholders = get_keyholders(DEFAULT_DATABASE_PATH)
    if keyholders is None:
        text = messages.START_USER_MENU_TEXT
    else:
        text = "\n\n".join([messages.current_key_holder_text(holder) for holder in keyholders])
    await edit_to_start_state(
        message,
        text,
        telegram_user_id=get_callback_telegram_user_id(query),
    )

async def handle_key_obtained(query: CallbackQuery, message: Message) -> None:
    await query.answer()
    key_count = get_key_count(DEFAULT_DATABASE_PATH)
    await message.edit_text(
        messages.KEY_CHOICE_PROMPT,
        reply_markup=build_key_obtained_receiver_key_choice_keyboard(key_count))

async def handle_key_obtained_choice(query: CallbackQuery, message: Message) -> None:
    await query.answer()
    key_id = parse_key_id_callback(query.data,RECEIVER_HANDOVER_KEY_CHOICE_CALLBACK_PREFIX)
    await handle_pending_handover_obtained_backend(key_id,query,message,edit_to_start_state)

async def handle_key_handover_callback(query: CallbackQuery,message: Message) -> None:
    await query.answer()
    telegram_id = get_callback_telegram_user_id(query)
    #TODO: now it first reads database to fetch id of the key holder holds and then
    # it later checks if holder actually holds the key -> needles double check
    #that uses query to database -> remake whenever possible
    key_id = get_key_id_by_telegram_user_id(DEFAULT_DATABASE_PATH,telegram_id)
    await handle_key_handover(key_id, query, message, edit_to_start_state)

async def handle_key_obtained_confirmation(query: CallbackQuery,message: Message) -> None:
    await query.answer()
    key_id = parse_key_id_callback(query.data,RECEIVER_KEY_HANDOVER_CONFIRM_CALLBACK)
    await handle_pending_handover_confirmation(key_id,query,message,edit_to_start_state)

async def handle_key_obtained_cancellation(query: CallbackQuery,message: Message) -> None:
    await query.answer()
    await edit_to_start_state(query.message,messages.START_USER_MENU_TEXT,query.from_user.id)

async def handle_unknown_callback(query: CallbackQuery, message: Message) -> None:
    await query.answer()
    await edit_to_start_state(message,messages.CALLBACK_USER_UNKNOWN_TEXT,
                                 telegram_user_id=get_callback_telegram_user_id(query)
    )
    
async def handle_holder_key_handover_cancellation(query: CallbackQuery, message: Message):
  await query.answer()
  telegram_id = get_callback_telegram_user_id(query)
  key_id = get_key_id_by_telegram_user_id(DEFAULT_DATABASE_PATH,telegram_id)
  await handle_pending_handover_cancellation(key_id,query,message)

async def handle_key_return_mailbox(query: CallbackQuery, message: Message) -> None:
    await query.answer()
    return_instruction = get_key_return_instruction(
        DEFAULT_DATABASE_PATH,
        get_callback_telegram_user_id(query),
    )
    if return_instruction is None:
        await edit_to_start_state(
            message,
            #TODO logically if we are not keyholder, we shouldn't even see this keyboard,handler
            messages.MAILBOX_HOLDER_BLOCKED_TEXT,
            get_callback_telegram_user_id(query),
        )
        return

    await message.edit_text(
        messages.MAILBOX_HOLDER_RETURN_INSTRUCTION_TEXT.format(
            key_id=return_instruction.key_id,
            room_number=return_instruction.room_number,
        ),
        reply_markup=build_key_return_mailbox_returned_keyboard(
            return_instruction.key_id,
        ),
    )

async def handle_key_return_mailbox_choice(query: CallbackQuery, message: Message) -> None:
    await query.answer()
    key_id = parse_key_id_callback(
        query.data,
        HOLDER_KEY_RETURN_MAILBOX_KEY_CHOICE_CALLBACK_PREFIX,
    )
    await message.edit_text(
        messages.MAILBOX_HOLDER_RETURN_PROMPT.format(key_id=key_id),
        reply_markup=build_key_return_mailbox_confirmation_keyboard(key_id),
    )

async def handle_key_return_mailbox_confirmation(query: CallbackQuery,message: Message) -> None:
    telegram_user_id = get_callback_telegram_user_id(query)
    key_id = parse_key_id_callback(
        query.data,
        HOLDER_KEY_RETURN_MAILBOX_CONFIRM_CALLBACK_PREFIX,
    )
    result = return_key_to_mailbox(DEFAULT_DATABASE_PATH, telegram_user_id, key_id)
    if result.status == ReturnToMailboxStatus.RETURNED:
        reply = messages.MAILBOX_HOLDER_RETURNED_TEXT.format(key_id=key_id)
    else:
        reply = messages.MAILBOX_HOLDER_BLOCKED_TEXT
    await query.answer()
    await edit_to_start_state(message,reply,telegram_user_id)

async def handle_key_return_mailbox_cancellation(query: CallbackQuery,message: Message) -> None:
    await query.answer()
    await edit_to_start_state(message,messages.HOLDER_CHANGE_CANCELLED_TEXT,
        get_callback_telegram_user_id(query))

async def handle_key_obtained_from_mailbox(query: CallbackQuery,message: Message) -> None:
    await query.answer()
    key_count = get_key_count(DEFAULT_DATABASE_PATH)
    await message.edit_text(
        messages.KEY_CHOICE_PROMPT,
        reply_markup=build_key_obtained_mailbox_key_choice_keyboard(key_count),
    )
    
async def handle_key_obtained_from_mailbox_choice(query: CallbackQuery,message: Message) -> None:
    await query.answer()
    key_id = parse_key_id_callback(
        query.data,
        RECEIVER_MAILBOX_KEY_CHOICE_CALLBACK_PREFIX,
    )
    
    message_text = messages.MAILBOX_RECEIVER_TAKE_PROMPT.format(key_id=key_id)
    await message.edit_text(
        message_text,
        reply_markup=build_key_obtained_mailbox_confirmation_keyboard(key_id)
    )
    
async def handle_key_obtained_from_mailbox_confirmation(query: CallbackQuery,message: Message) -> None:
    telegram_user_id = get_callback_telegram_user_id(query)
    key_id = parse_key_id_callback(
        query.data,
        RECEIVER_MAILBOX_KEY_OBTAINED_CONFIRM_CALLBACK_PREFIX,
    )
    mailbox = get_key_owner_mailbox_info(DEFAULT_DATABASE_PATH, key_id)
    result = take_key_from_mailbox(DEFAULT_DATABASE_PATH,telegram_user_id,key_id,mailbox.id)
    if result.status == TakeFromMailboxStatus.TAKEN:
        reply = messages.MAILBOX_RECEIVER_TAKEN_TEXT.format(key_id=key_id)
    elif result.status == TakeFromMailboxStatus.KEY_NOT_IN_MAILBOX:
        reply = messages.MAILBOX_RECEIVER_EMPTY_TEXT.format(key_id=key_id)
    else:
        reply = messages.AUTH_USER_UNREGISTERED_TEXT
    await query.answer()
    await edit_to_start_state(message, reply, telegram_user_id)

async def handle_key_obtained_from_mailbox_cancellation(query: CallbackQuery,message: Message) -> None:
    await query.answer()
    await edit_to_start_state(
        message,
        messages.MAILBOX_RECEIVER_CANCELLED_TEXT,
        get_callback_telegram_user_id(query))

CALLBACK_HANDLERS: dict[str, CallbackHandler] = {
    RECEIVER_KEY_INFO_CALLBACK: handle_key_request,
    RECEIVER_HANDOVER_KEY_OBTAINED_CALLBACK: handle_key_obtained,
    RECEIVER_MAILBOX_KEY_OBTAINED_CALLBACK: handle_key_obtained_from_mailbox,
    RECEIVER_MAILBOX_KEY_OBTAINED_CANCEL_CALLBACK: handle_key_obtained_from_mailbox_cancellation,
    HOLDER_KEY_HANDOVER_CALLBACK: handle_key_handover_callback,
    RECEIVER_KEY_HANDOVER_CONFIRM_CALLBACK: handle_key_obtained_confirmation,
    RECEIVER_KEY_HANDOVER_CANCEL_CALLBACK: handle_key_obtained_cancellation,
    HOLDER_KEY_HANDOVER_CANCEL_CALLBACK: handle_holder_key_handover_cancellation,
    HOLDER_KEY_RETURN_MAILBOX_CALLBACK: handle_key_return_mailbox,
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
    application.add_handler(CommandHandler("mytelegramid", my_telegram_id_command_handler))
    application.add_handler(CommandHandler("clear", clear_command_handler))
    application.add_handler(CommandHandler("givekey", give_key_command_handler))
    application.add_handler(CommandHandler("adduser", add_user_command_handler))
    application.add_handler(CommandHandler("updateuser", update_user_command_handler))
    application.add_handler(CommandHandler("users", users_command_handler))
    application.add_handler(CommandHandler("keyhistory", key_history_command_handler))
    application.add_handler(CommandHandler("keystatus", key_status_command_handler))
    application.add_handler(CommandHandler("activatekey", activate_key_command_handler))
    application.add_handler(CommandHandler("deactivatekey", deactivate_key_command_handler))
    application.add_handler(CommandHandler("help", help_command_handler))
    application.add_handler(CallbackQueryHandler(callback_query_handler))
    print("Telegram Bot started!", flush=True)
    application.run_polling()
