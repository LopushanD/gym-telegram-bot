from src.key_service import KeyHolder


START_STATE_TEXT = "Welcome! The buttons are ready."

LOOKING_UP_KEY_HOLDER = "Looking up the key holder..."
NO_KEY_REGISTERED = "No key is registered in the database yet."

PLEASE_CONFIRM_KEY_OBTAINED = "Please confirm."
KEY_OBTAINED_CONFIRMATION_PROMPT = "Please confirm that you got the key."

HANDOVER_NOT_ALLOWED_ANSWER = "Only the current holder can hand over the key."
HANDOVER_NOT_ALLOWED_TEXT = "Only the current key holder can start a handover."
HANDOVER_READY_ANSWER = "Ready for handover."
HANDOVER_READY_TEXT = (
    "Give the key to the next member and ask them to press Got the key."
)
HANDOVER_COMPLETED_ANSWER = "Handover completed."
HANDOVER_COMPLETED_TEXT = "The key was handed over from {from_member} to {to_member}."
HANDOVER_CONFIRMATION_PROMPT = (
    "Please confirm that you got the key from {from_member}."
)
HANDOVER_FAILED_TEXT = (
    "The handover procedure failed. You remain the recorded key holder."
)
HANDOVER_ALREADY_PENDING_ANSWER = "Handover already pending."
HANDOVER_ALREADY_PENDING_TEXT = (
    "A handover is already pending. Ask the next member to press Got the key."
)
HANDOVER_SELF_CONFIRMATION_ANSWER = "Ask the next member to press Got the key."
HANDOVER_SELF_CONFIRMATION_TEXT = (
    "The current holder cannot complete their own handover."
)

MISSING_TELEGRAM_USER_ANSWER = "Could not identify you."
MISSING_TELEGRAM_USER_TEXT = (
    "Could not confirm key ownership because Telegram user is missing."
)
UNREGISTERED_USER_ANSWER = "You are not registered."
UNREGISTERED_USER_TEXT = (
    "Could not confirm key ownership because you are not registered."
)
KEY_OBTAINED_CONFIRMED_ANSWER = "Confirmed."
KEY_OBTAINED_CONFIRMED_TEXT = "Confirmed. You are now recorded as the key holder."

KEY_OBTAINED_CANCELLED_ANSWER = "Cancelled."
KEY_OBTAINED_CANCELLED_TEXT = "Cancelled. No key-obtained action was recorded."

UNKNOWN_CALLBACK_ANSWER = "Unknown button."
UNKNOWN_CALLBACK_TEXT = "Unknown button. Back to the start."


def current_key_holder_text(holder: KeyHolder) -> str:
    return (
        f"The key is currently held by {holder.name} {holder.surname}, "
        f"room {holder.room_number}."
    )
