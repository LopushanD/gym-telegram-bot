from src.config import HANDOVER_WINDOW_SECONDS
from src.models import KeyHolder

# Message constants use WHAT_POV_ACTION_KIND.
START_USER_MENU_TEXT = "Choose what you want to do."
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
AUTH_USER_MISSING_TEXT = "Could not identify your Telegram user."
AUTH_USER_UNREGISTERED_TEXT = "You are not registered as a gym member."
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


def mailbox_receiver_take_prompt(key_id: int) -> str:
    return f"Confirm that you received key {key_id} from the mailbox."


def current_key_holder_text(holder: KeyHolder) -> str:
    member = holder.member
    text = (
        f"Key {holder.key_id} is currently held by {member.full_name}, "
        f"room {member.room_number}."
    )
    if member.telegram_name:
        telegram_name = member.telegram_name
        if not telegram_name.startswith("@"):
            telegram_name = f"@{telegram_name}"
        text += f"\nTelegram: {telegram_name}"
    if member.phone_number:
        text += f"\nPhone: {member.phone_number}"
    return text
