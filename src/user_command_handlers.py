from telegram import Update
from telegram.error import TelegramError

from src import messages
from src.config import DEFAULT_DATABASE_PATH,TELEGRAM_MESSAGE_LIMIT
from src.telegram_helpers import get_update_telegram_user_id
from src.database import get_gym_member_records,GymMember
from src.user_commands import *

CLEAR_BATCH_SIZE = 100

def _process_admin_records(members: list[GymMember], separator: str) -> list[str]:
    replies = []
    for member in members:
        record = " ".join(["Name:",member.full_name,"Room:",str(member.room_number),
        "Telegram username:",member.telegram_name if member.telegram_name is not None else "-"]) 
        #checks if message length is enough or another message is needed to fit everything
        if replies and len(replies[-1]) + len(separator) + len(record) <= TELEGRAM_MESSAGE_LIMIT:
            replies[-1] += separator + record
        else:
            replies.append(record)
    return replies

async def _delete_deletable_messages(bot, chat_id: int, message_ids: list[int]) -> bool:
    """Delete what Telegram permits and report whether any deletion request succeeded."""
    try:
        await bot.delete_messages(chat_id=chat_id, message_ids=message_ids)
        return True
    except TelegramError:
        if len(message_ids) == 1:
            return False

    middle = len(message_ids) // 2
    newer_deleted = await _delete_deletable_messages(bot, chat_id, message_ids[middle:])
    if not newer_deleted:
        return False

    older_deleted = await _delete_deletable_messages(bot, chat_id, message_ids[:middle])
    return newer_deleted or older_deleted

async def help_command_handler(update: Update, context) -> None:
    await update.effective_message.reply_text(HELP_TEXT,parse_mode="MarkdownV2")

async def my_telegram_id_command_handler(update: Update, context) -> None:
    telegram_user_id = get_update_telegram_user_id(update)
    if telegram_user_id is None:
        await update.effective_message.reply_text(messages.AUTH_USER_MISSING_TEXT)
    else:
        await update.effective_message.reply_text(
            messages.MY_TELEGRAM_ID_TEXT.format(telegram_user_id=telegram_user_id))

async def tutorials_tutorial_command_handler(update: Update, context) -> None:
    message = update.effective_message
    await message.reply_text(load_user_tutorial(TUTORIALS_INFO_TUTORIAL),parse_mode="MarkdownV2")

async def user_regestration_tutorial_command_handler(update: Update, context) -> None:
    message = update.effective_message
    await message.reply_text(load_user_tutorial(REGESTRATION_TUTORIAL),parse_mode="MarkdownV2")

async def get_key_tutorial_command_handler(update: Update, context) -> None:
    message = update.effective_message
    await message.reply_text(load_user_tutorial(GET_KEY_TUTORIAL),parse_mode="MarkdownV2")

async def give_key_tutorial_command_handler(update: Update, context) -> None:
    message = update.effective_message
    await message.reply_text(load_user_tutorial(GIVE_KEY_TUTORIAL),parse_mode="MarkdownV2")

async def return_key_tutorial_command_handler(update: Update, context) -> None:
    message = update.effective_message
    await message.reply_text(load_user_tutorial(RETURN_KEY_TUTORIAL),parse_mode="MarkdownV2")

async def show_admins_command_handler(update: Update, context) -> None:
    message = update.effective_message
    members = get_gym_member_records(DEFAULT_DATABASE_PATH,is_admin=True)
    if members:
        for reply in _process_admin_records(members, "\n\n"):
            await message.reply_text(reply)
    else:
        await message.reply_text(messages.USER_COMMAND_ADMINS_NOT_FOUND_TEXT)
        
async def clear_command_handler(update: Update, context) -> None:
    message = update.effective_message
    chat = update.effective_chat
    last_message_id = message.message_id
    while last_message_id > 0:
        # telegram deletes messages in batches with certain max size
        first_message_id = max(1, last_message_id - CLEAR_BATCH_SIZE + 1)
        deleted_any = await _delete_deletable_messages(
            context.bot,
            chat.id,
            list(range(first_message_id, last_message_id + 1)),
        )
        if not deleted_any:
            break
        last_message_id = first_message_id - 1
