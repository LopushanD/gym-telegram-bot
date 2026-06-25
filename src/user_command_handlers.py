from telegram import Update
from telegram.error import TelegramError

from src import messages
from src.telegram_helpers import get_update_telegram_user_id
from src.user_commands import *

CLEAR_BATCH_SIZE = 100

async def delete_deletable_messages(bot, chat_id: int, message_ids: list[int]) -> bool:
    """Delete what Telegram permits and report whether any deletion request succeeded."""
    try:
        await bot.delete_messages(chat_id=chat_id, message_ids=message_ids)
        return True
    except TelegramError:
        if len(message_ids) == 1:
            return False

    middle = len(message_ids) // 2
    newer_deleted = await delete_deletable_messages(bot, chat_id, message_ids[middle:])
    if not newer_deleted:
        return False

    older_deleted = await delete_deletable_messages(bot, chat_id, message_ids[:middle])
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

async def clear_command_handler(update: Update, context) -> None:
    message = update.effective_message
    chat = update.effective_chat
    last_message_id = message.message_id
    while last_message_id > 0:
        # telegram deletes messages in batches with certain max size
        first_message_id = max(1, last_message_id - CLEAR_BATCH_SIZE + 1)
        deleted_any = await delete_deletable_messages(
            context.bot,
            chat.id,
            list(range(first_message_id, last_message_id + 1)),
        )
        if not deleted_any:
            break
        last_message_id = first_message_id - 1
