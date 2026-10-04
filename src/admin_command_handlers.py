from telegram import Update
from src import messages
from src.config import DATABASE_PATH,LAST_N_RECORDS_DEFAULT,gym_member_record_separator
from src.admin_commands import *
from src.command_handlers_utility import *
from src.database import (
    GymMemberAlreadyExistsError,
    add_gym_member,
    get_gym_member_by_telegram_user_id,
    query_gym_member_records,
    get_key_history,
    get_key_status,
    set_key_active,
    set_key_owner,
    set_admin,
    update_gym_member,
)
from src.handover_flow import cancel_pending_handover
from src.key_service import GiveKeyStatus, give_key_to_member
from src.telegram_helpers import get_update_telegram_user_id

async def reply_with_command_documentation(message, command_name: str) -> None:
    await message.reply_text(
        load_command_documentation(command_name),
        parse_mode="MarkdownV2",
    )
async def _user_is_admin(update:Update)->bool:
    message = update.effective_message
    requesting_member = get_gym_member_by_telegram_user_id(
        DATABASE_PATH,
        get_update_telegram_user_id(update))
    if requesting_member is None:
        await message.reply_text(messages.AUTH_USER_UNREGISTERED_TEXT)
        return False
    if not requesting_member.is_admin:
        await message.reply_text(messages.ADMIN_COMMAND_FORBIDDEN_TEXT)
        return False
    return True

async def set_admin_command_handler(update: Update, context) -> None:
    message = update.effective_message
    if not await _user_is_admin(update):
        return
    arguments = getattr(context, "args", [])
    if is_help_request(arguments):
        await reply_with_command_documentation(message, SET_ADMIN_ADMIN_COMMAND)
        return
    if len(arguments) != 2:
        await message.reply_text(messages.ADMIN_SET_ADMIN_USAGE_TEXT)
        return
    try:
        telegram_user_id = int(arguments[0])
    except ValueError:
        await message.reply_text(messages.ADMIN_SET_ADMIN_BAD_VALUE_TEXT)
        return
    admin_set_value = arguments[1].lower()
    if telegram_user_id <= 0 or admin_set_value not in ("true", "false"):
        await message.reply_text(messages.ADMIN_SET_ADMIN_BAD_VALUE_TEXT)
        return
    admin_set_value = admin_set_value == "true" #transform value to boolean
    members = set_admin(DATABASE_PATH, telegram_user_id, admin_set_value)
    if not members: # there can be 0 or 1 user with given telegram ID
        await message.reply_text(
            messages.ADMIN_SET_ADMIN_NOT_FOUND_TEXT.format(telegram_user_id=telegram_user_id)
        )
        return
    await message.reply_text(
        messages.ADMIN_SET_ADMIN_COMPLETED_TEXT.format(
            member = process_gym_member_records(members,"",showAdminStatus=True)[0]
        )
    )

async def add_user_command_handler(update: Update, context) -> None:
    message = update.effective_message
    if not await _user_is_admin(update):
        return
    arguments = getattr(context, "args", [])
    if is_help_request(arguments):
        await reply_with_command_documentation(message, ADD_USER_ADMIN_COMMAND)
        return

    if len(arguments) != 5:
        await message.reply_text(messages.ADMIN_ADD_USER_USAGE_TEXT)
        return

    try:
        telegram_user_id = int(arguments[0])
        room_number = int(arguments[3])
    except ValueError:
        await message.reply_text(messages.ADMIN_BAD_VALUE_TEXT)
        return

    if telegram_user_id <= 0 or room_number <= 0:
        await message.reply_text(messages.ADMIN_BAD_VALUE_TEXT)
        return

    reply = None
    try:
        new_user = GymMember(
            telegram_user_id=telegram_user_id,
            name=arguments[1],
            surname=arguments[2],
            room_number=room_number,
            telegram_name=arguments[4])
        add_gym_member(DATABASE_PATH,new_user)
    except GymMemberAlreadyExistsError:
        reply = messages.ADMIN_ADD_USER_ALREADY_EXISTS_TEXT.format(
            telegram_user_id=telegram_user_id,
        )
    except Exception:
        reply = messages.UNKNOWN_EXCEPTION
    else:
        reply = messages.ADMIN_ADD_USER_COMPLETED_TEXT.format(
            member=new_user.full_name,
            telegram_user_id=telegram_user_id,
            room_number=room_number)
    await message.reply_text(reply)

async def get_all_commands_handler(update: Update, context) -> None:
    message = update.effective_message
    if not await _user_is_admin(update):
        return
    await reply_with_command_documentation(message, ALL_COMMANDS_ADMIN_COMMAND)

async def give_key_command_handler(update: Update, context) -> None:
    message = update.effective_message
    if not await _user_is_admin(update):
        return
    arguments = getattr(context, "args", [])
    if is_help_request(arguments):
        await reply_with_command_documentation(message, GIVE_KEY_ADMIN_COMMAND)
        return

    if len(arguments) != 2:
        await message.reply_text(messages.ADMIN_GIVE_KEY_USAGE_TEXT)
        return
    #================
    #TODO this block of code seems redundant and unnessesary
    try:
        key_id, telegram_user_id = (int(argument) for argument in arguments)
    except ValueError:
        await message.reply_text(messages.ADMIN_BAD_VALUE_TEXT)
        return

    if key_id <= 0 or telegram_user_id <= 0:
        await message.reply_text(messages.ADMIN_BAD_VALUE_TEXT)
        return
    #======================
    result = give_key_to_member(DATABASE_PATH, key_id, telegram_user_id)
    if result.status == GiveKeyStatus.USER_NOT_REGISTERED:
        reply = messages.ADMIN_GIVE_KEY_USER_NOT_REGISTERED_TEXT.format(
            telegram_user_id=telegram_user_id)
    elif result.status == GiveKeyStatus.KEY_NOT_FOUND:
        reply = messages.KEY_NOT_FOUND_TEXT.format(key_id=key_id)
    elif result.status == GiveKeyStatus.GIVEN:
        if result.member is None:
            raise ValueError("given key result is missing the target member")
        # TODO why do we need to cancel pending handover? just to be sure?
        cancel_pending_handover(key_id)
        reply = messages.ADMIN_GIVE_KEY_COMPLETED_TEXT.format(
            key_id=key_id,
            member=result.member.full_name,
            telegram_user_id=telegram_user_id,
        )
    else:
        raise ValueError(f"unsupported give key status: {result.status}")
    await message.reply_text(reply)

async def change_key_owner_command_handler(update: Update, context) -> None:
    message = update.effective_message
    if not await _user_is_admin(update):
        return
    arguments = getattr(context, "args", [])
    if is_help_request(arguments):
        await reply_with_command_documentation(message, CHANGE_KEY_OWNER_ADMIN_COMMAND)
        return

    if len(arguments) != 2:
        await message.reply_text(messages.ADMIN_CHANGE_KEY_OWNER_USAGE_TEXT)
        return

    try:
        key_id, telegram_user_id = (int(argument) for argument in arguments)
    except ValueError:
        await message.reply_text(messages.ADMIN_BAD_VALUE_TEXT)
        return
    if key_id <= 0 or telegram_user_id <= 0:
        await message.reply_text(messages.ADMIN_BAD_VALUE_TEXT)
        return

    member = get_gym_member_by_telegram_user_id(DATABASE_PATH, telegram_user_id)
    if member is None:
        await message.reply_text(
            messages.ADMIN_CHANGE_KEY_OWNER_USER_NOT_REGISTERED_TEXT.format(
                telegram_user_id=telegram_user_id,
            )
        )
        return

    if not set_key_owner(DATABASE_PATH, key_id, member.id):
        await message.reply_text(messages.KEY_NOT_FOUND_TEXT.format(key_id=key_id))
        return

    await message.reply_text(
        messages.ADMIN_CHANGE_KEY_OWNER_COMPLETED_TEXT.format(
            key_id=key_id,
            member=member.full_name,
            telegram_user_id=telegram_user_id,
        )
    )


async def update_user_command_handler(update: Update, context) -> None:
    message = update.effective_message
    if not await _user_is_admin(update):
        return
    arguments = getattr(context, "args", [])
    if is_help_request(arguments):
        await reply_with_command_documentation(message, UPDATE_USER_ADMIN_COMMAND)
        return

    try:
        member_update = parse_update_user_command_arguments(arguments)
    except UpdateUserUsageError:
        await message.reply_text(messages.ADMIN_UPDATE_USER_USAGE_TEXT)
        return
    except ValueError as error:
        await message.reply_text(messages.ADMIN_BAD_VALUE_TEXT)
        return
    member_before = get_gym_member_by_telegram_user_id(
        DATABASE_PATH,member_update.telegram_user_id)
    if member_before is None:
        await message.reply_text(
            messages.ADMIN_UPDATE_USER_NOT_FOUND_TEXT.format(
                telegram_user_id=member_update.telegram_user_id))
        return
    member_after = update_gym_member(
        DATABASE_PATH,member_update)[0]
    changes = format_gym_member_changes(member_before, member_after)
    if not changes:
        reply = messages.ADMIN_UPDATE_USER_NO_CHANGES_TEXT.format(
            telegram_user_id=member_update.telegram_user_id)
    else:
        reply = messages.ADMIN_UPDATE_USER_COMPLETED_TEXT.format(
            telegram_user_id=member_update.telegram_user_id,
            changes=changes)
    await message.reply_text(reply)

async def users_command_handler(update: Update, context) -> None:
    message = update.effective_message
    if not await _user_is_admin(update):
        return
    arguments = getattr(context, "args", [])
    if is_help_request(arguments):
        await reply_with_command_documentation(message, SHOW_USERS_ADMIN_COMMAND)
        return
    
    try:
        gym_member_dict = parse_user_command_arguments(arguments)
        members = query_gym_member_records(
            DATABASE_PATH,
            GymMember(name=gym_member_dict["name"],
            surname=gym_member_dict["surname"],
            room_number=gym_member_dict["room_number"]))
        if members:
            for reply in process_gym_member_records(members,gym_member_record_separator,showTechnicalIDs=True,showMemberStatus=True,showAdminStatus=True):
                await message.reply_text(reply)
        else:
            await message.reply_text(messages.ADMIN_USERS_NOT_FOUND_TEXT)
    except UserCommandUsageError:
        await message.reply_text(messages.ADMIN_USERS_USAGE_TEXT)
    except ValueError as e:
        await message.reply_text(str(e))

async def key_history_command_handler(update: Update, context) -> None:
    message = update.effective_message
    if not await _user_is_admin(update):
        return
    arguments = getattr(context, "args", [])
    if is_help_request(arguments):
        await reply_with_command_documentation(message, SHOW_KEY_HISTORY_ADMIN_COMMAND)
        return

    if not 1 <= len(arguments) <= 2:
        await message.reply_text(messages.ADMIN_KEY_HISTORY_USAGE_TEXT)
        return

    try:
        key_id = int(arguments[0])
        limit = int(arguments[1]) if len(arguments) == 2 else LAST_N_RECORDS_DEFAULT
    except ValueError:
        await message.reply_text(messages.ADMIN_BAD_VALUE_TEXT)
        return
    if key_id <= 0 or limit <= 0:
        await message.reply_text(messages.ADMIN_BAD_VALUE_TEXT)
        return

    records = get_key_history(DATABASE_PATH, key_id, limit)
    if records:
        replies = process_key_history_records(records,"\n"+"-"*10+"\n")
        for reply in replies:
            await message.reply_text(reply)
    else:
        await message.reply_text(messages.ADMIN_KEY_HISTORY_NOT_FOUND_TEXT)

async def key_status_command_handler(update: Update, context) -> None:
    message = update.effective_message
    if not await _user_is_admin(update):
        return
    arguments = getattr(context, "args", [])
    if is_help_request(arguments):
        await reply_with_command_documentation(message, SHOW_KEY_STATUS_ADMIN_COMMAND)
        return

    if len(arguments) != 1:
        await message.reply_text(messages.ADMIN_KEY_STATUS_USAGE_TEXT)
        return

    try:
        key_id = int(arguments[0])
    except ValueError:
        await message.reply_text(messages.ADMIN_BAD_VALUE_TEXT)
        return
    if key_id <= 0:
        await message.reply_text(messages.ADMIN_BAD_VALUE_TEXT)
        return
    key,holder,owner = get_key_status(DATABASE_PATH, key_id)
    if key is None:
        await message.reply_text(
            messages.KEY_NOT_FOUND_TEXT.format(key_id=key_id))
        return
    elif holder is None or owner is None:
        await message.reply_text(f"Current holder or owner of the key were not found. It shouldn't be like that. Please, report the situation to admins.")
        return
    await message.reply_text(messages.key_status_text(key,holder,owner))

async def set_key_active_command_handler(
    update: Update,
    context,
    *,
    do_activate: bool) -> None:
    message = update.effective_message
    if not await _user_is_admin(update):
        return
    arguments = getattr(context, "args", [])
    if is_help_request(arguments):
        command_name = (
            ACTIVATE_KEY_ADMIN_COMMAND
            if do_activate
            else DEACTIVATE_KEY_ADMIN_COMMAND
        )
        await reply_with_command_documentation(message, command_name)
        return

    if len(arguments) != 1:
        usage = (
            messages.ADMIN_ACTIVATE_KEY_USAGE_TEXT
            if do_activate
            else messages.ADMIN_DEACTIVATE_KEY_USAGE_TEXT
        )
        await message.reply_text(usage)
        return

    try:
        key_id = int(arguments[0])
    except ValueError:
        await message.reply_text(messages.ADMIN_BAD_VALUE_TEXT)
        return
    if key_id <= 0:
        await message.reply_text(messages.ADMIN_BAD_VALUE_TEXT)
        return

    if not set_key_active(DATABASE_PATH, key_id, do_activate):
        await message.reply_text(messages.KEY_NOT_FOUND_TEXT.format(key_id=key_id))
        return

    reply = (
        messages.ADMIN_ACTIVATE_KEY_COMPLETED_TEXT
        if do_activate
        else messages.ADMIN_DEACTIVATE_KEY_COMPLETED_TEXT)
    await message.reply_text(reply.format(key_id=key_id))
    
# Adapters to make handlers compatible with Telegram API
async def activate_key_command_handler(update: Update, context) -> None:
    await set_key_active_command_handler(update, context, do_activate=True)

async def deactivate_key_command_handler(update: Update, context) -> None:
    await set_key_active_command_handler(update, context, do_activate=False)
