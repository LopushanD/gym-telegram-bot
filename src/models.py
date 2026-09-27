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


@dataclass(frozen=True)
class KeyStatus:
    key_id: int
    current_holder: GymMember
    owner: GymMember
    is_active: bool


@dataclass(frozen=True)
class KeyHistoryRecord:
    event_id: int
    key_id: int
    member: GymMember
    taken_at: datetime
