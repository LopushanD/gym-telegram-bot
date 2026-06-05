from dataclasses import dataclass


@dataclass(frozen=True)
class GymMember:
    id: int
    telegram_user_id: int
    name: str
    surname: str
    room_number: int
    telegram_name: str | None
    phone_number: str | None
    is_admin: bool

    @property
    def full_name(self) -> str:
        return f"{self.name} {self.surname}"


@dataclass(frozen=True)
class KeyHolder:
    key_id: int
    member: GymMember
