from src.config import TELEGRAM_MESSAGE_LIMIT
from src.models import GymMember, KeyHistoryRecord
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

def _split_record_texts(record_texts: list[str], separator: str) -> list[str]:
    replies = []
    for record_text in record_texts:
        #checks if message length is enough or another message is needed to fit everything
        if replies and len(replies[-1]) + len(separator) + len(record_text) <= TELEGRAM_MESSAGE_LIMIT:
            replies[-1] += separator + record_text
        else:
            replies.append(record_text)
    return replies

def process_gym_member_records(members: list[GymMember], separator: str) -> list[str]:
    replies = []
    records = []
    for member in members:
        record = "\n".join([
        "Gym member ID: "+str(member.id),"Name: "+member.full_name,
        "Room: "+str(member.room_number),
        "Telegram username: "+member.telegram_name if member.telegram_name is not None else "Telegram username: None",
        "Telegram ID: "+str(member.telegram_user_id)])
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
    return (
        f"{record.taken_at:%Y-%m-%d %H:%M:%S} UTC: "
        f"key {record.key_id} received by {record.member.full_name}, "
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
    

def is_help_request(arguments: list[str]) -> bool:
    return len(arguments) == 1 and arguments[0] in HELP_OPTIONS

class UpdateUserUsageError(ValueError):
    pass
def parse_update_user_command_arguments(arguments: list[str]) -> tuple[int, dict[str, str | int]]:
    if len(arguments) < 3 or len(arguments[1:]) % 2 != 0:
        raise UpdateUserUsageError

    try:
        telegram_user_id = int(arguments[0])
    except ValueError as error:
        raise ValueError("telegram user ID must be an integer") from error
    if telegram_user_id <= 0:
        raise ValueError("telegram user ID must be positive")

    updates: dict[str, str | int] = {}
    for option, value in zip(arguments[1::2], arguments[2::2]):
        field = GYM_MEMBER_OPTION_FIELDS.get(option)
        if field is None or field in updates or value.startswith("-"):
            raise UpdateUserUsageError
        updates[field] = value

    if "room_number" in updates:
        try:
            room_number = int(updates["room_number"])
        except ValueError as error:
            raise ValueError("room number must be an integer") from error
        if room_number <= 0:
            raise ValueError("room number must be positive")
        updates["room_number"] = room_number
    return telegram_user_id, updates

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