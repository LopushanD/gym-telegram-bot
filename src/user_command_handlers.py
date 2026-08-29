from telegram import Update
from telegram.ext import ContextTypes
import asyncio
from src.bot_replies import reply_with_start_state
from src import messages
from src.config import DEFAULT_DATABASE_PATH
from src.telegram_helpers import get_update_telegram_user_id
from src.database import get_gym_member_records
from src.command_handlers_utility import process_gym_member_records
from src.user_commands import *

DELETE_LAST_N_MESSAGES = 90

async def start_state_command_handler(update: Update, context:ContextTypes.DEFAULT_TYPE) -> None:
    await reply_with_start_state(
        update.effective_message,
        messages.START_USER_MENU_TEXT,
        telegram_user_id=get_update_telegram_user_id(update),
    )

async def help_command_handler(update: Update, context:ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(HELP_TEXT,parse_mode="MarkdownV2")

async def my_telegram_id_command_handler(update: Update, context:ContextTypes.DEFAULT_TYPE) -> None:
    telegram_user_id = get_update_telegram_user_id(update)
    if telegram_user_id is None:
        await update.effective_message.reply_text(messages.AUTH_USER_MISSING_TEXT)
    else:
        await update.effective_message.reply_text(
            messages.MY_TELEGRAM_ID_TEXT.format(telegram_user_id=telegram_user_id))

async def tutorials_tutorial_command_handler(update: Update, context:ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    await message.reply_text(load_user_tutorial(TUTORIALS_INFO_TUTORIAL),parse_mode="MarkdownV2")

async def user_regestration_tutorial_command_handler(update: Update, context:ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    await message.reply_text(load_user_tutorial(REGESTRATION_TUTORIAL),parse_mode="MarkdownV2")

async def get_key_tutorial_command_handler(update: Update, context:ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    await message.reply_text(load_user_tutorial(GET_KEY_TUTORIAL),parse_mode="MarkdownV2")

async def give_key_tutorial_command_handler(update: Update, context:ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    await message.reply_text(load_user_tutorial(GIVE_KEY_TUTORIAL),parse_mode="MarkdownV2")

async def return_key_tutorial_command_handler(update: Update, context:ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    await message.reply_text(load_user_tutorial(RETURN_KEY_TUTORIAL),parse_mode="MarkdownV2")

async def show_admins_command_handler(update: Update, context:ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    members = get_gym_member_records(DEFAULT_DATABASE_PATH,is_admin=True)
    if members:
        for reply in process_gym_member_records(members, "\n"+"-"*10+"\n"):
            await message.reply_text(reply)
    else:
        await message.reply_text(messages.USER_COMMAND_ADMINS_NOT_FOUND_TEXT)
#this command may cause problems with message rendering (telegram local database doesn't properly sync with the cloud).
# It can be fixed by deleting cache on the user side (cannot infuence it).
# It also can be mitigated by giving telegram some time to sync via sleep().
async def clear_command_handler(update: Update, context:ContextTypes.DEFAULT_TYPE) -> None:
    last_message = update.effective_message
    chat = update.effective_chat
    min_id = max(1,last_message.message_id - DELETE_LAST_N_MESSAGES)
    await chat.delete_messages(list(range(min_id,last_message.id+1)))
    await asyncio.sleep(1)
    await reply_with_start_state(last_message,telegram_user_id=get_update_telegram_user_id(update))