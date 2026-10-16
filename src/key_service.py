from dataclasses import dataclass
from enum import Enum

from src.config import DATABASE_PATH
from src.models import GymMember, KeyHolder, Key
from src.database import (
    change_key_holder,
    get_key_status,
    get_current_keyholder_info,
    get_all_current_keyholders_info,
    get_key_return_instruction_info,
    get_gym_member_by_telegram_user_id,

    get_key_owner_mailbox_info,
    query_key_table,
    query_gym_member_records,
    update_key_table,
)

class KeyUpdateMemberNotFoundError(ValueError):
    def __init__(self, telegram_user_id: int):
        self.telegram_user_id = telegram_user_id
        super().__init__(f"No gym member is registered with Telegram ID {telegram_user_id}")


@dataclass(frozen=True)
class KeyUpdateResult:
    key_before: Key
    key_after: Key

    @property
    def invalidates_pending_handover(self) -> bool:
        before, after = self.key_before, self.key_after
        return (
            before.current_holder_id != after.current_holder_id
            or before.is_in_mailbox != after.is_in_mailbox
            or (before.is_active is True and after.is_active is False)
        )


@dataclass(frozen=True)
class KeyReturnInstruction:
    key_label: str
    key_id: int
    room_number: int

class HandoverStatus(Enum):
    READY = "ready"
    NOT_CURRENT_HOLDER = "not_current_holder"


class ReturnToMailboxStatus(Enum):
    RETURNED = "returned"
    NOT_CURRENT_HOLDER = "not_current_holder"


class TakeFromMailboxStatus(Enum):
    TAKEN = "taken"
    KEY_NOT_IN_MAILBOX = "key_not_in_mailbox"
    MISSING_TELEGRAM_USER = "missing_telegram_user"
    USER_NOT_REGISTERED = "user_not_registered"
    KEY_NOT_FOUND = "key_not_found"


class GiveKeyStatus(Enum):
    GIVEN = "given"
    KEY_NOT_FOUND = "key_not_found"
    USER_NOT_REGISTERED = "user_not_registered"


@dataclass(frozen=True)
class HandoverResult:
    status: HandoverStatus


@dataclass(frozen=True)
class ReturnToMailboxResult:
    status: ReturnToMailboxStatus


@dataclass(frozen=True)
class TakeFromMailboxResult:
    status: TakeFromMailboxStatus


@dataclass(frozen=True)
class GiveKeyResult:
    status: GiveKeyStatus
    member: GymMember | None = None


def get_keyholders(database_path)-> list[KeyHolder]:
    holders = get_all_current_keyholders_info(database_path)
    if not holders:
        return None
    return holders

def get_key_return_instruction(database_path, telegram_user_id):
    if telegram_user_id is None:
        return None

    instruction = get_key_return_instruction_info(database_path, telegram_user_id)
    if instruction is None:
        return None

    key_id,key_name,owner_room_number = instruction
    return KeyReturnInstruction(Key(key_id=key_id,name=key_name).label,key_id, owner_room_number)

def user_currently_holds_key(database_path, telegram_user_id, key_id):
    if telegram_user_id is None:
        return False
    holder = get_current_keyholder_info(database_path, key_id, telegram_user_id)
    return holder is not None and not holder.key.is_in_mailbox

def user_currently_holds_any_key(database_path, telegram_user_id)-> bool:
    if telegram_user_id is None:
        return False
    holders = get_all_current_keyholders_info(database_path, telegram_user_id)
    #list should consist of 1 holder, but edge cases with admin commands can happen
    return any(not holder.key.is_in_mailbox for holder in holders)


def can_start_key_handover(database_path, telegram_user_id, key_id):
    if user_currently_holds_key(database_path, telegram_user_id, key_id):
        return HandoverResult(status=HandoverStatus.READY)
    return HandoverResult(status=HandoverStatus.NOT_CURRENT_HOLDER)

def return_key_to_mailbox(database_path,telegram_user_id,key_id):
    if user_currently_holds_key(database_path, telegram_user_id, key_id):
        mailbox = get_key_owner_mailbox_info(database_path, key_id)
        change_key_holder(database_path, key_id, mailbox.id, is_in_mailbox=True)
        return ReturnToMailboxResult(status=ReturnToMailboxStatus.RETURNED)
    return ReturnToMailboxResult(status=ReturnToMailboxStatus.NOT_CURRENT_HOLDER)

def take_key_from_mailbox(database_path,telegram_user_id,key_id):
    if telegram_user_id is None:
        return TakeFromMailboxResult(status=TakeFromMailboxStatus.MISSING_TELEGRAM_USER)
    member = get_gym_member_by_telegram_user_id(database_path, telegram_user_id)
    if member is None:
        return TakeFromMailboxResult(status=TakeFromMailboxStatus.USER_NOT_REGISTERED)
    key, _, _ = get_key_status(database_path, key_id)
    if key is None or not key.is_active:
        return TakeFromMailboxResult(status=TakeFromMailboxStatus.KEY_NOT_FOUND)
    if not key.is_in_mailbox:
        return TakeFromMailboxResult(status=TakeFromMailboxStatus.KEY_NOT_IN_MAILBOX)
    change_key_holder(database_path, key_id, member.id)
    return TakeFromMailboxResult(status=TakeFromMailboxStatus.TAKEN)


def give_key_to_member(database_path, key_id, telegram_user_id, is_in_mailbox: bool = False):
    """Record that specified member or their mailbox holds key."""
    member = get_gym_member_by_telegram_user_id(database_path, telegram_user_id)
    if member is None:
        return GiveKeyResult(status=GiveKeyStatus.USER_NOT_REGISTERED)

    if get_current_keyholder_info(database_path, key_id) is None:
        return GiveKeyResult(status=GiveKeyStatus.KEY_NOT_FOUND)

    change_key_holder(database_path, key_id, member.id, is_in_mailbox=is_in_mailbox)
    return GiveKeyResult(status=GiveKeyStatus.GIVEN, member=member)

def update_key(database_path, key_update: Key) -> KeyUpdateResult | None:
    """Update a key after checking member references and record responsibility changes."""
    #key is already checked at this point
    keys = query_key_table(database_path, Key(key_id=key_update.key_id))
    if not keys:
        return None
    updated_keys = update_key_table(database_path, key_update, record_holder_history=True)
    if not updated_keys:
        raise ValueError("Updated key was not found")
    return KeyUpdateResult(keys[0], updated_keys[0])


def get_key_label(database_path, key_id: int) -> str:
    """Resolve a key's display label; unknown IDs have no name to display."""
    keys = query_key_table(database_path, Key(key_id=key_id))
    return keys[0].label if keys else str(key_id)
