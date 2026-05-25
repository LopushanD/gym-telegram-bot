from dataclasses import dataclass
from enum import Enum

from src.config import MAILBOX_MEMBER_ID
from src.database import (
    change_key_holder,
    get_current_key_holder_info,
    get_gym_member_id_by_telegram_user_id,
)

@dataclass(frozen=True)
class KeyHolder:
    name: str
    surname: str
    room_number: int
    telegram_name: str | None
    phone_number: str | None

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


@dataclass(frozen=True)
class HandoverResult:
    status: HandoverStatus


@dataclass(frozen=True)
class ReturnToMailboxResult:
    status: ReturnToMailboxStatus


@dataclass(frozen=True)
class TakeFromMailboxResult:
    status: TakeFromMailboxStatus


def get_key_holder(database_path, key_id):
    holder = get_current_key_holder_info(database_path, key_id=key_id)
    if holder is None:
        return None
    name, surname, room_number, telegram_name, phone_number = holder
    return KeyHolder(name, surname, room_number, telegram_name, phone_number)

def user_currently_holds_key(database_path, telegram_user_id, key_id):
    if telegram_user_id is None:
        return False
    return get_current_key_holder_info(database_path,key_id,telegram_user_id) is not None

def can_start_key_handover(database_path, telegram_user_id, key_id):
    if user_currently_holds_key(database_path, telegram_user_id, key_id):
        return HandoverResult(status=HandoverStatus.READY)
    return HandoverResult(status=HandoverStatus.NOT_CURRENT_HOLDER)

def return_key_to_mailbox(database_path,telegram_user_id,key_id,mailbox_member_id=MAILBOX_MEMBER_ID):
    if user_currently_holds_key(database_path, telegram_user_id, key_id):
        change_key_holder(database_path, key_id, mailbox_member_id)
        return ReturnToMailboxResult(status=ReturnToMailboxStatus.RETURNED)
    return ReturnToMailboxResult(status=ReturnToMailboxStatus.NOT_CURRENT_HOLDER)


def take_key_from_mailbox(database_path,telegram_user_id,key_id,mailbox_member_id):
    if get_current_key_holder_info(database_path,key_id,
        gym_member_id=mailbox_member_id) is None:
        return TakeFromMailboxResult(status=TakeFromMailboxStatus.KEY_NOT_IN_MAILBOX)
    if telegram_user_id is None:
        return TakeFromMailboxResult(status=TakeFromMailboxStatus.MISSING_TELEGRAM_USER)
    member_id = get_gym_member_id_by_telegram_user_id(database_path, telegram_user_id)
    if member_id is None:
        return TakeFromMailboxResult(status=TakeFromMailboxStatus.USER_NOT_REGISTERED)
    change_key_holder(database_path, key_id, member_id)
    return TakeFromMailboxResult(status=TakeFromMailboxStatus.TAKEN)
