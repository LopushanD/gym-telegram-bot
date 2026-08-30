from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class GymMember:
    id: int
    telegram_user_id: int
    name: str
    surname: str
    room_number: int
    telegram_name: str | None
    is_admin: bool

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
