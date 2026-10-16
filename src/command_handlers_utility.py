from src.config import TELEGRAM_MESSAGE_LIMIT
from src.models import GymMember, Key, KeyHistoryRecord
from src.database import get_gym_member_by_telegram_user_id, query_gym_member_records
from src.key_service import KeyUpdateMemberNotFoundError
HELP_OPTIONS = {"-h", "--help"}
GYM_MEMBER_OPTION_FIELDS = {
    "-n": "name",
    "--name": "name",
    "-s": "surname",
    "--surname": "surname",
    "-r": "room_number",
    "--room": "room_number",
    "-t": "telegram_name",
    "--telegram-name": "telegram_name",
}
GYM_MEMBER_FIELD_LABELS = {
    "name": "Name",
    "surname": "Surname",
    "room_number": "Room",
    "telegram_name": "Telegram name",
}
KEY_OPTION_FIELDS = {
    "-c": "current_holder_id",
    "--current-holder": "current_holder_id",
    "-o": "owner_member_id",
    "--owner": "owner_member_id",
    "-a": "is_active",
    "--activate": "is_active",
    "-n": "name",
    "--name": "name",
    "-m": "is_in_mailbox",
    "--mailbox": "is_in_mailbox",
}
KEY_FIELD_LABELS = {
    "current_holder_id": "Current holder Telegram ID",
    "owner_member_id": "Owner Telegram ID",
    "is_active": "Active",
    "name": "Name",
    "is_in_mailbox": "In mailbox",
}

def _split_record_texts(record_texts: list[str], separator: str) -> list[str]:
    replies = []
    for record_text in record_texts:
        #checks if message length is enough or another message is needed to fit everything
        if replies and len(replies[-1]) + len(separator) + len(record_text) <= TELEGRAM_MESSAGE_LIMIT:
            replies[-1] += separator + record_text
        else:
            replies.append(record_text)
    return replies

def process_gym_member_records(members: list[GymMember], separator: str,showTechnicalIDs: bool = False, showMemberStatus:bool = False,showAdminStatus=False) -> list[str]:
    replies = []
    records = []
    for member in members:
        record = "\n".join([
        "Name: "+member.full_name,
        "Room: "+str(member.room_number),
        "Telegram username: "+member.telegram_name if member.telegram_name is not None else "Telegram username: None"])
        if showTechnicalIDs:
            record = "\n".join([record,
            "Telegram ID: "+str(member.telegram_user_id),
            "Gym member ID: "+str(member.id)])
        if showAdminStatus:
            record = "\n".join([record,
            f"is admin: {member.is_admin}"])
        if showMemberStatus:
            record = "\n".join([record,
            "Suspended until: "+member.suspended_until if member.suspended_until is not None else "Suspended until: None",
            "Deleted at: "+member.deleted_at if member.deleted_at is not None else "Deleted at: None"])
        records.append(record)
    replies = _split_record_texts(records,separator)
    return replies

def process_key_history_records(records: list[KeyHistoryRecord],separator:str)->list[str]:
    replies = []
    record_texts = [_key_history_record_text(record) for record in records]
    for reply in _split_record_texts(record_texts, separator):
        replies.append(reply)
    return replies 


def _key_history_record_text(record: KeyHistoryRecord) -> str:
    transfer = "put into mailbox of" if record.put_into_mailbox else "received by"
    return (
        f"{record.taken_at:%Y-%m-%d %H:%M:%S}: "
        f"key {record.key.label} {transfer} {record.member.full_name}, "
        f"room {record.member.room_number} "
        f"{record.member.telegram_name}"
    )

def format_gym_member_changes(
    member_before: GymMember,
    member_after: GymMember,
) -> str:
    return "\n".join(
        f"{label}: {getattr(member_before, field)} -> {getattr(member_after, field)}"
        for field, label in GYM_MEMBER_FIELD_LABELS.items()
        if getattr(member_before, field) != getattr(member_after, field)
    )

def format_key_changes(key_before: Key, key_after: Key, database_path) -> str:
    def display_value(key: Key, field: str):
        value = getattr(key, field)
        if field in ("current_holder_id", "owner_member_id"):
            members = query_gym_member_records(database_path, GymMember(id=value))
            if not members:
                raise ValueError(f"Key references missing gym member {value}")
            return members[0].telegram_user_id
        return value

    return "\n".join(
        f"{label}: {display_value(key_before, field)} -> {display_value(key_after, field)}"
        for field, label in KEY_FIELD_LABELS.items()
        if getattr(key_before, field) != getattr(key_after, field)
    )

def is_help_request(arguments: list[str]) -> bool:
    for argument in arguments:
        if argument in HELP_OPTIONS:
            return True
    return False

class GiveKeyUsageError(ValueError):
    pass

def parse_give_key_command_arguments(arguments: list[str]) -> tuple[int, int, bool]:
    if len(arguments) not in (2, 4):
        raise GiveKeyUsageError
    if len(arguments) == 4 and arguments[2] not in ("-m", "--mailbox"):
        raise GiveKeyUsageError

    key_id, telegram_user_id = (int(argument) for argument in arguments[:2])
    if key_id <= 0 or telegram_user_id <= 0:
        raise ValueError("Key ID and Telegram ID must be positive")
    #This parameter must default to False
    is_in_mailbox = False
    if len(arguments) == 4:
        mailbox_value = arguments[3].lower()
        if mailbox_value not in ("true", "false"):
            raise ValueError("-m/--mailbox must be True or False")
        is_in_mailbox = mailbox_value == "true"
    return key_id, telegram_user_id, is_in_mailbox

class UpdateUserUsageError(ValueError):
    pass
def parse_update_user_command_arguments(arguments: list[str]) -> GymMember:
    if len(arguments) < 3 or len(arguments[1:]) % 2 != 0:
        raise UpdateUserUsageError
    telegram_user_id = _check_and_typecast_id(arguments[0],"Telegram ID")
    updates: dict[str, str | int] = {"telegram_user_id":telegram_user_id}
    for option, value in zip(arguments[1::2], arguments[2::2]):
        field = GYM_MEMBER_OPTION_FIELDS.get(option)
        if field is None or field in updates or value.startswith("-"):
            raise UpdateUserUsageError
        if field == "room_number":
            value = int(value)
            if value <= 0:
                raise ValueError(f"{field} must be positive")
        updates[field] = value
    return GymMember(**updates)

class UpdateKeyUsageError(ValueError):
    pass

def _check_and_typecast_id(value: str, label: str) -> int:
    identifier = int(value)
    if not 0 < identifier <= 2**63 - 1:
        raise ValueError(f"{label} must be a positive 64-bit integer")
    return identifier

def parse_update_key_command_arguments(arguments: list[str], database_path) -> Key:
    if len(arguments) < 3 or len(arguments[1:]) % 2 != 0:
        raise UpdateKeyUsageError
    key_id = _check_and_typecast_id(arguments[0], "Key ID")
    updates: dict[str, str | int | bool] = {"key_id": key_id}
    for option, value in zip(arguments[1::2], arguments[2::2]):
        field = KEY_OPTION_FIELDS.get(option)
        if field is None or field in updates or value.startswith("-"):
            raise UpdateKeyUsageError
        if field in ("current_holder_id", "owner_member_id"):
            telegram_id = _check_and_typecast_id(value, f"{option} Telegram ID")
            member = get_gym_member_by_telegram_user_id(database_path, telegram_id)
            if member is None:
                raise KeyUpdateMemberNotFoundError(telegram_id)
            value = member.id
        elif field in ("is_active", "is_in_mailbox"):
            if value.lower() not in ("true", "false"):
                raise ValueError(f"{option} must be True or False")
            value = value.lower() == "true"
        elif not value.strip(): # at this point it can be only "name" field
            raise ValueError("Key name must not be blank")
        updates[field] = value
    return Key(**updates) # matches parameters and values on it's own


class UserCommandUsageError(ValueError):
    pass

def parse_user_command_arguments(arguments: list[str]) -> dict[str, str | None]:
    if len(arguments) % 2 != 0:
        raise UserCommandUsageError
    result: dict[str, str|None] = {"name":None,"surname":None,"room_number":None}
    for option, value in zip(arguments[0::2], arguments[1::2]):
        field = GYM_MEMBER_OPTION_FIELDS.get(option)
        if field is None or field not in result.keys() or value.startswith("-"):
            raise UserCommandUsageError
        else:
            result[field] = value
    if result["room_number"] is not None:
        room_number = result["room_number"]
        #TODO change to actual highest number
        HIGHEST_DORM_ROOM_NUMBER = 2330
        if room_number.isdecimal() and int(room_number) > 0 \
            and int(room_number) <=HIGHEST_DORM_ROOM_NUMBER: 
            return result
        else:   
            raise ValueError("Room number must be a positive number and"+\
                " cannot exceed highest room number in the dorm")
    return result