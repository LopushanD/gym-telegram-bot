from dataclasses import dataclass
from enum import Enum

from src.database import (
    change_key_holder,
    get_current_key_holder,
    get_gym_member_id_by_telegram_user_id,
)

@dataclass(frozen=True)
class KeyHolder:
    name: str
    surname: str
    room_number: int

class HandoverStatus(Enum):
    READY = "ready"
    NOT_CURRENT_HOLDER = "not_current_holder"

@dataclass(frozen=True)
class HandoverResult:
    status: HandoverStatus

def get_key_holder(database_path, key_id):
    holder = get_current_key_holder(database_path, key_id=key_id)
    if holder is None:
        return None

    name, surname, room_number = holder
    return KeyHolder(name=name, surname=surname, room_number=room_number)

def user_currently_holds_key(database_path, telegram_user_id, key_id):
    if telegram_user_id is None:
        return False

    return get_current_key_holder(
        database_path,
        key_id=key_id,
        telegram_user_id=telegram_user_id,
    ) is not None

def can_start_key_handover(database_path, telegram_user_id, key_id):
    if not user_currently_holds_key(database_path, telegram_user_id, key_id):
        return HandoverResult(status=HandoverStatus.NOT_CURRENT_HOLDER)

    return HandoverResult(status=HandoverStatus.READY)