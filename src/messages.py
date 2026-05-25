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
HANDOVER_RECEIVER_MISSING_TEXT = "No handover is waiting for confirmation."

HANDOVER_RECEIVER_SELF_TEXT = "You cannot confirm a handover from yourself."
AUTH_USER_MISSING_TEXT = "Could not identify your Telegram user."
AUTH_USER_UNREGISTERED_TEXT = "You are not registered as a gym member."
KEY_RECEIVER_RECORDED_TEXT = "Recorded: you received the key."

MAILBOX_HOLDER_BLOCKED_TEXT = "Only the current key holder can do that."
MAILBOX_HOLDER_RETURN_PROMPT = confirmation_prompt(
    "Record that you returned the key to the mailbox."
)
HANDOVER_HOLDER_CANCELLED_TEXT = "Cancelled. No key holder change was recorded."
MAILBOX_HOLDER_CANCELLED_TEXT = "Cancelled. No key holder change was recorded."

MAILBOX_HOLDER_RETURNED_TEXT = "Recorded: the key was returned to the mailbox."
MAILBOX_RECEIVER_TAKE_PROMPT = confirmation_prompt(
    "Record that you received the key from the mailbox."
)
MAILBOX_RECEIVER_CANCELLED_TEXT = "Cancelled. No key holder change was recorded."
MAILBOX_RECEIVER_TAKEN_TEXT = "Recorded: you received the key from the mailbox."
MAILBOX_RECEIVER_EMPTY_TEXT = "The key is not recorded as being in the mailbox."

CALLBACK_USER_UNKNOWN_TEXT = "Unknown button. Back to the start."


def current_key_holder_text(holder: KeyHolder) -> str:
    text = (
        f"The key is currently held by {holder.name} {holder.surname}, "
        f"room {holder.room_number}."
    )
    if holder.telegram_name:
        text += f"\nTelegram: @{holder.telegram_name}"
    if holder.phone_number:
        text += f"\nPhone: {holder.phone_number}"
    return text
