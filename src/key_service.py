from dataclasses import dataclass
from enum import Enum

from src.config import DEFAULT_DATABASE_PATH
from src.models import GymMember, KeyHolder
from src.database import (
    change_key_holder,
    get_current_keyholder_info,
    get_all_current_keyholders_info,
    get_key_count,
    get_key_return_instruction_info,
    get_gym_member_by_telegram_user_id,
    get_gym_member_id_by_telegram_user_id,
    get_key_owner_mailbox_info
)

@dataclass(frozen=True)
class KeyReturnInstruction:
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


def get_tracked_key_count(database_path) -> int:
    return get_key_count(database_path)

def get_key_return_instruction(database_path, telegram_user_id):
    if telegram_user_id is None:
        return None

    instruction = get_key_return_instruction_info(database_path, telegram_user_id)
    if instruction is None:
        return None

    key_id, room_number = instruction
    return KeyReturnInstruction(key_id=key_id, room_number=room_number)

def user_currently_holds_key(database_path, telegram_user_id, key_id):
    if telegram_user_id is None:
        return False
    return get_current_keyholder_info(database_path,key_id,telegram_user_id) is not None

def user_currently_holds_any_key(database_path, telegram_user_id)-> bool:
    #if given telegram_user doesn't hold any keys -> empty list returned
    if telegram_user_id is None or not get_all_current_keyholders_info(database_path,telegram_user_id):
        return False
    return True


def can_start_key_handover(database_path, telegram_user_id, key_id):
    if user_currently_holds_key(database_path, telegram_user_id, key_id):
        return HandoverResult(status=HandoverStatus.READY)
    return HandoverResult(status=HandoverStatus.NOT_CURRENT_HOLDER)

def return_key_to_mailbox(database_path,telegram_user_id,key_id):
    if user_currently_holds_key(database_path, telegram_user_id, key_id):
        mailbox = get_key_owner_mailbox_info(DEFAULT_DATABASE_PATH, key_id)
        change_key_holder(database_path, key_id, mailbox.id)
        return ReturnToMailboxResult(status=ReturnToMailboxStatus.RETURNED)
    return ReturnToMailboxResult(status=ReturnToMailboxStatus.NOT_CURRENT_HOLDER)


def take_key_from_mailbox(database_path,telegram_user_id,key_id,mailbox_member_id):
    if get_current_keyholder_info(database_path,key_id,
        gym_member_id=mailbox_member_id) is None:
        return TakeFromMailboxResult(status=TakeFromMailboxStatus.KEY_NOT_IN_MAILBOX)
    if telegram_user_id is None:
        return TakeFromMailboxResult(status=TakeFromMailboxStatus.MISSING_TELEGRAM_USER)
    member_id = get_gym_member_id_by_telegram_user_id(database_path, telegram_user_id)
    if member_id is None:
        return TakeFromMailboxResult(status=TakeFromMailboxStatus.USER_NOT_REGISTERED)
    change_key_holder(database_path, key_id, member_id)
    return TakeFromMailboxResult(status=TakeFromMailboxStatus.TAKEN)


def give_key_to_member(database_path, key_id, telegram_user_id):
    member = get_gym_member_by_telegram_user_id(database_path, telegram_user_id)
    if member is None:
        return GiveKeyResult(status=GiveKeyStatus.USER_NOT_REGISTERED)

    if get_current_keyholder_info(database_path, key_id) is None:
        return GiveKeyResult(status=GiveKeyStatus.KEY_NOT_FOUND)

    change_key_holder(database_path, key_id, member.id)
    return GiveKeyResult(status=GiveKeyStatus.GIVEN, member=member)
