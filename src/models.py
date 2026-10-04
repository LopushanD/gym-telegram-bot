from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=False)
class GymMember:
    id: int | None = None
    telegram_user_id: int | None = None
    name: str | None = None
    surname: str | None = None
    room_number: int | None = None
    telegram_name: str | None = None
    is_admin: bool | None = None
    suspended_until:str | None = None
    deleted_at:str | None = None

    @property
    def full_name(self) -> str:
        return f"{self.name} {self.surname}"


@dataclass(frozen=True)
class KeyHolder:
    key_id: int
    member: GymMember


@dataclass(frozen=False)
class Key:
    key_id: int | None = None
    current_holder_id: int | None = None
    owner_member_id: int | None = None
    is_active: bool | None = None


@dataclass(frozen=True)
class KeyHistoryRecord:
    event_id: int
    key_id: int
    member: GymMember
    taken_at: datetime
