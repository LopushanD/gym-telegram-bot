from src.config import HANDOVER_WINDOW_SECONDS,TELEGRAM_CONTACT_NAME
from src.models import GymMember, KeyHistoryRecord, KeyHolder, KeyStatus
from src.user_commands import TUTORIALS_INFO_TUTORIAL

UNKNOWN_EXCEPTION = "Unknown error occured."
# Message constants use WHAT_POV_ACTION_KIND.
START_USER_MENU_TEXT = (
    "Welcome to the gym key tracking bot.\n\n"
    f"to get usage instructions, use /{TUTORIALS_INFO_TUTORIAL}. Read those, if you do not know, what to do. For available commands, use /help."
    "\n\nAdmins can use /commands to see all available commands for admins. \n\n"
    f"Found a bug or have a suggestion? Contact {TELEGRAM_CONTACT_NAME}."
)
USER_TUTORIAL_EMPTY_TEXT = "The tutorial is not available yet."
USER_COMMAND_ADMINS_NOT_FOUND_TEXT = "There are currently no active gym AG members."
KEY_RECEIVER_CONFIRM_NOTICE = "Confirm before recording."
KEY_RECEIVER_RECORD_PROMPT = "Confirm that you received key {key_id} from {from_member}."

HANDOVER_HOLDER_BLOCKED_TEXT = "Only the current key holder can do that."
HANDOVER_HOLDER_STARTED_TEXT = f"Handover started. Give the key to the next member and ask them to confirm it in the bot within {HANDOVER_WINDOW_SECONDS} seconds.."

HANDOVER_BOTH_COMPLETED_TEXT = "Recorded: {to_member} received key {key_id} from {from_member}."
HANDOVER_RECEIVER_CONFIRM_PROMPT = "Confirm that you received the key from {from_member}."
HANDOVER_HOLDER_EXPIRED_TEXT = "The handover expired before the receiver confirmed it. You are still recorded as the holder."
HANDOVER_HOLDER_PENDING_TEXT = "Key {key_id} already has a pending handover. Wait for the receiver to confirm it, or cancel the handover."
HANDOVER_RECEIVER_MISSING_TEXT = "No pending handover was found for key {key_id}. Ask the current holder to start the handover."

HANDOVER_RECEIVER_SELF_TEXT = "You cannot confirm a handover from yourself."
AUTH_USER_MISSING_TEXT = "Could not identify your Telegram id."
AUTH_USER_UNREGISTERED_TEXT = "You are not registered as a gym member."
MY_TELEGRAM_ID_TEXT = "Your Telegram ID is {telegram_user_id}."
KEY_RECEIVER_RECORDED_TEXT = "Recorded: you received the key."

MAILBOX_HOLDER_BLOCKED_TEXT = "You cannot hand over key {key_id} because you are not its recorded holder."
MAILBOX_HOLDER_RETURN_PROMPT = "Confirm that you returned key {key_id} to the mailbox."

MAILBOX_HOLDER_RETURN_INSTRUCTION_TEXT = "Return key {key_id} to the mailbox for room {room_number}."

HOLDER_CHANGE_CANCELLED_TEXT = "Cancelled. No key holder change was recorded."

MAILBOX_HOLDER_RETURNED_TEXT = "Recorded: the key {key_id} was returned to the mailbox."
KEY_CHOICE_PROMPT = "Which key did you receive? Select the number written on the key."
MAILBOX_RECEIVER_TAKE_PROMPT = "Confirm that you received key {key_id} from the mailbox."
# MAILBOX_RECEIVER_KEY_REQUIRED_TEXT = "Choose a key before confirming."
MAILBOX_RECEIVER_CANCELLED_TEXT = "Cancelled. No key holder change was recorded."
MAILBOX_RECEIVER_TAKEN_TEXT = "Recorded: You are now the holder of key {key_id}."
MAILBOX_RECEIVER_EMPTY_TEXT = "Key {key_id} is currently recorded as being held not by mailbox, but by someone else. Check 'Key holder info'."

CALLBACK_USER_UNKNOWN_TEXT = "Unknown button. Back to the start."
ADMIN_BAD_VALUE_TEXT = "Entered value is not valid"
ADMIN_COMMAND_FORBIDDEN_TEXT = "Only admins can use this command."
ADMIN_GIVE_KEY_USAGE_TEXT = "Usage: /givekey key_id telegram_id"
ADMIN_CHANGE_KEY_OWNER_USAGE_TEXT = "Usage: /keychangeowner key_id telegram_id"
ADMIN_CHANGE_KEY_OWNER_USER_NOT_REGISTERED_TEXT = "No gym member is registered with Telegram ID {telegram_user_id}."
ADMIN_CHANGE_KEY_OWNER_COMPLETED_TEXT = "Recorded: key {key_id} is now owned by {member} (Telegram ID {telegram_user_id})."
ADMIN_GIVE_KEY_USER_NOT_REGISTERED_TEXT = "No gym member is registered with Telegram ID {telegram_user_id}."
KEY_NOT_FOUND_TEXT = "Key {key_id} does not exist."
ADMIN_GIVE_KEY_COMPLETED_TEXT = "Recorded: key {key_id} was given to {member} (Telegram ID {telegram_user_id})."
ADMIN_ADD_USER_USAGE_TEXT = "Usage: /adduser telegram_id name surname room telegram_name"
ADMIN_ADD_USER_ALREADY_EXISTS_TEXT = "A gym member with Telegram ID {telegram_user_id} already exists."
ADMIN_ADD_USER_COMPLETED_TEXT = "Added gym member {member} (Telegram ID {telegram_user_id}), room {room_number}."
ADMIN_UPDATE_USER_USAGE_TEXT = (
    "Usage: /updateuser telegram_id option value [option value ...]\n"
    "Options: -n/--name, -s/--surname, -r/--room, "
    "-t/--telegram-name"
)
ADMIN_UPDATE_USER_NOT_FOUND_TEXT = "No gym member is registered with Telegram ID {telegram_user_id}."
ADMIN_UPDATE_USER_NO_CHANGES_TEXT = "No user data changed for Telegram ID {telegram_user_id}."
ADMIN_UPDATE_USER_COMPLETED_TEXT = "Updated gym member with Telegram ID {telegram_user_id}:\n{changes}"
ADMIN_USERS_USAGE_TEXT = "Usage: /users [-n or --name Value] [-s or --surname Value] [-n or --room Value]"
ADMIN_USERS_NOT_FOUND_TEXT = "No gym members matched the query."
ADMIN_KEY_HISTORY_USAGE_TEXT = "Usage: /keyhistory key_id [last_n_records]"
ADMIN_KEY_HISTORY_NOT_FOUND_TEXT = "key holder history was not found."
ADMIN_KEY_STATUS_USAGE_TEXT = "Usage: /keystatus key_id"
ADMIN_ACTIVATE_KEY_USAGE_TEXT = "Usage: /activatekey key_id"
ADMIN_DEACTIVATE_KEY_USAGE_TEXT = "Usage: /deactivatekey key_id"
ADMIN_ACTIVATE_KEY_COMPLETED_TEXT = "Activated key {key_id}."
ADMIN_DEACTIVATE_KEY_COMPLETED_TEXT = "Deactivated key {key_id}."

def mailbox_receiver_take_prompt(key_id: int) -> str:
    return f"Confirm that you received key {key_id} from the mailbox."


def current_key_holder_text(holder: KeyHolder) -> str:
    member = holder.member
    text = (
        f"Key {holder.key_id} is currently held by {member.full_name}, "
        f"room {member.room_number}."
    )
    if member.telegram_name is None:
        telegram_name = "None"
    else:
        telegram_name = member.telegram_name
        if not telegram_name.startswith("@"):
            telegram_name = f"@{telegram_name}"
    text += f"\nTelegram name: {telegram_name}"
    return text

# TODO I think it's better to get rid of this function and make local
# functions that format records as needed  
def gym_member_record_text(member: GymMember) -> str:
    return " ".join(
        (
            f"ID: {member.id}",
            f"Telegram ID: {member.telegram_user_id}",
            f"Name: {member.name}",
            f"Surname: {member.surname}",
            f"Room: {member.room_number}",
            f"Telegram name: {member.telegram_name or 'None'}",
            f"Admin: {'yes' if member.is_admin else 'no'}",
        )
    )
# TODO just like function above, think about moving such procesing functions to command_handlers_utility.py file
# or creating dedicated file formatting functions 
def key_status_text(status: KeyStatus) -> str:
    return "\n".join(
        (
            f"Key ID: {status.key_id}\nActive: {'yes' if status.is_active else 'no'}",
            f"Current holder:\n{gym_member_record_text(status.current_holder)}",
            f"Owner:\n{gym_member_record_text(status.owner)}",
        )
    )
