from dataclasses import dataclass
from enum import Enum

from config import DEFAULT_KEY_ID
from database import (
    get_current_key_holder,
    get_gym_member_id_by_telegram_user_id,
    on_holder_change,
)


@dataclass(frozen=True)
class KeyHolder:
    name: str
    surname: str
    room_number: int


class ConfirmKeyStatus(Enum):
    CONFIRMED = "confirmed"
    MISSING_TELEGRAM_USER = "missing_telegram_user"
    USER_NOT_REGISTERED = "user_not_registered"


class HandoverStatus(Enum):
    READY = "ready"
    NOT_CURRENT_HOLDER = "not_current_holder"


@dataclass(frozen=True)
class ConfirmKeyResult:
    status: ConfirmKeyStatus


@dataclass(frozen=True)
class HandoverResult:
    status: HandoverStatus


def get_key_holder(database_path, key_id=DEFAULT_KEY_ID):
    holder = get_current_key_holder(database_path, key_id=key_id)
    if holder is None:
        return None

    name, surname, room_number = holder
    return KeyHolder(name=name, surname=surname, room_number=room_number)


def user_currently_holds_key(database_path, telegram_user_id, key_id=DEFAULT_KEY_ID):
    if telegram_user_id is None:
        return False

    return get_current_key_holder(
        database_path,
        key_id=key_id,
        telegram_user_id=telegram_user_id,
    ) is not None


def start_key_handover(database_path, telegram_user_id, key_id=DEFAULT_KEY_ID):
    if not user_currently_holds_key(database_path, telegram_user_id, key_id):
        return HandoverResult(status=HandoverStatus.NOT_CURRENT_HOLDER)

    return HandoverResult(status=HandoverStatus.READY)


def confirm_key_obtained(database_path, telegram_user_id, key_id=DEFAULT_KEY_ID):
    if telegram_user_id is None:
        return ConfirmKeyResult(status=ConfirmKeyStatus.MISSING_TELEGRAM_USER)

    member_id = get_gym_member_id_by_telegram_user_id(
        database_path,
        telegram_user_id,
    )
    if member_id is None:
        return ConfirmKeyResult(status=ConfirmKeyStatus.USER_NOT_REGISTERED)

    on_holder_change(database_path, key_id, member_id)
    return ConfirmKeyResult(status=ConfirmKeyStatus.CONFIRMED)
