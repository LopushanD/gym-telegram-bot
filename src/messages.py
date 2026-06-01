from src.key_service import KeyHolder


def confirmation_prompt(action: str) -> str:
    return f"Confirm this action?\n\n{action}"


# Message constants use WHAT_POV_ACTION_KIND.
START_USER_MENU_TEXT = "Choose what you want to do."
KEY_RECEIVER_CONFIRM_NOTICE = "Confirm before recording."
KEY_RECEIVER_RECORD_PROMPT = confirmation_prompt(
    "Record that you received the key."
)
HANDOVER_HOLDER_BLOCKED_TEXT = "Only the current key holder can do that."
HANDOVER_HOLDER_STARTED_TEXT = (
    "Handover started. Give the key to the next member and ask them to confirm receipt."
)
HANDOVER_BOTH_COMPLETED_TEXT = "Recorded: {to_member} received the key from {from_member}."
HANDOVER_RECEIVER_CONFIRM_PROMPT = confirmation_prompt(
    "Record that you received the key from {from_member}."
)
HANDOVER_HOLDER_EXPIRED_TEXT = "Handover expired. No key holder change was recorded."
HANDOVER_HOLDER_PENDING_TEXT = "A handover is already waiting for confirmation."
HANDOVER_RECEIVER_MISSING_TEXT = "There's no handover for key {key_id}."

HANDOVER_RECEIVER_SELF_TEXT = "You cannot confirm a handover from yourself."
AUTH_USER_MISSING_TEXT = "Could not identify your Telegram user."
AUTH_USER_UNREGISTERED_TEXT = "You are not registered as a gym member."
KEY_RECEIVER_RECORDED_TEXT = "Recorded: you received the key."

MAILBOX_HOLDER_BLOCKED_TEXT = "Only the current key holder can do that."
MAILBOX_HOLDER_RETURN_PROMPT = confirmation_prompt(
    "Record that you returned key {key_id} to the mailbox."
)
MAILBOX_HOLDER_RETURN_INSTRUCTION_TEXT = (
    "You need to return key {key_id} to room's {room_number} mailbox."
)
HOLDER_CHANGE_CANCELLED_TEXT = "Cancelled. No key holder change was recorded."

MAILBOX_HOLDER_RETURNED_TEXT = "Recorded: the key was returned to the mailbox."
KEY_CHOICE_PROMPT = "Which key"
MAILBOX_RECEIVER_TAKE_PROMPT = confirmation_prompt(
    "Record that you received key {key_id} from the mailbox."
)
# MAILBOX_RECEIVER_KEY_REQUIRED_TEXT = "Choose a key before confirming."
MAILBOX_RECEIVER_CANCELLED_TEXT = "Cancelled. No key holder change was recorded."
MAILBOX_RECEIVER_TAKEN_TEXT = "Recorded: you received the key from the mailbox."
MAILBOX_RECEIVER_EMPTY_TEXT = "The key is not recorded as being in the mailbox."

CALLBACK_USER_UNKNOWN_TEXT = "Unknown button. Back to the start."


def mailbox_receiver_take_prompt(key_id: int) -> str:
    return confirmation_prompt(f"Record that you received key {key_id} from the mailbox.")


def current_key_holder_text(holder: KeyHolder) -> str:
    surname = holder.surname
    text = (
        f"Key {holder.key_id} is currently held by {holder.name} {surname if surname is not None else ""}, "
        f"room {holder.room_number}."
    )
    if holder.telegram_name:
        telegram_name = holder.telegram_name
        if not telegram_name.startswith("@"):
            telegram_name = f"@{telegram_name}"
        text += f"\nTelegram: {telegram_name}"
    if holder.phone_number:
        text += f"\nPhone: {holder.phone_number}"
    return text
