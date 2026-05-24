from src.key_service import KeyHolder


START_STATE_TEXT = "Welcome! The buttons are ready."
PLEASE_CONFIRM_KEY_OBTAINED = "Please confirm."
KEY_OBTAINED_CONFIRMATION_PROMPT = "Please confirm that you got the key."
HANDOVER_NOT_ALLOWED_ANSWER = "Only the current holder can hand over the key."
HANDOVER_READY_ANSWER = "Give the key to the next member and ask them to press 'Got the key'."
HANDOVER_COMPLETED_ANSWER = "The key was handed over from {from_member} to {to_member}."
HANDOVER_CONFIRMATION_PROMPT = (
    "Please confirm that you got the key from {from_member}."
)
HANDOVER_FAILED_ANSWER = (
    "The handover procedure had timeout. You remain the key holder."
)
HANDOVER_ALREADY_PENDING_ANSWER = "A handover is already pending. Ask the next member to press Got the key."
HANDOVER_NO_PENDING_ANSWER = "There's no pending handover. Ask the key holder to start the handover."

HANDOVER_SELF_CONFIRMATION_ANSWER = "You cannot complete your own handover."
MISSING_TELEGRAM_USER_ANSWER = "Could not identify you."
UNREGISTERED_USER_ANSWER = "You are not registered as a gym member."
KEY_OBTAINED_CONFIRMED_ANSWER = "Confirmed. You are now recorded as the key holder."

KEY_OBTAINED_CANCELLED_ANSWER = "The handover was cancelled."
KEY_RETURN_MAILBOX_NOT_ALLOWED_ANSWER = "Only the current holder can return the key to the mailbox."
KEY_RETURN_MAILBOX_CONFIRMATION_PROMPT = "Please confirm you want return the key to the mailbox."
KEY_RETURNED_TO_MAILBOX_ANSWER = "The key was returned to the mailbox."
KEY_RETURN_MAILBOX_CANCELLED_ANSWER = "Returning the key to the mailbox was cancelled."
KEY_TAKEN_FROM_MAILBOX_ANSWER = "Confirmed. You are now the key holder."
KEY_NOT_IN_MAILBOX_ANSWER = "The key is not in the mailbox."

UNKNOWN_CALLBACK_ANSWER = "Unknown button. Back to the start."


def current_key_holder_text(holder: KeyHolder) -> str:
    return (
        f"The key is currently held by {holder.name} {holder.surname}, "
        f"room {holder.room_number}."
    )
