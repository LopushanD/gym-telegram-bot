import random
import sqlite3
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime
if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.models import GymMember, KeyHistoryRecord, KeyHolder, Key
from src.config import DATABASE_PATH


@contextmanager
def database_connection(database_path) -> Iterator[sqlite3.Connection]:
    """Commit or roll back the transaction, then always close the connection."""
    connection = sqlite3.connect(database_path)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


class GymMemberAlreadyExistsError(ValueError):
    pass
def _gym_member_from_row(row: sqlite3.Row, prefix: str|None = None) -> GymMember:
    member = GymMember(
        id=row["member_id"] if prefix is None else row[f"{prefix}_member_id"],
        telegram_user_id=row["telegram_user_id"] if prefix is None else row[f"{prefix}_telegram_user_id"],
        name=row["name"] if prefix is None else row[f"{prefix}_name"],
        surname=row["surname"] if prefix is None else row[f"{prefix}_surname"],
        room_number=row["room_number"] if prefix is None else row[f"{prefix}_room_number"],
        telegram_name=row["telegram_name"] if prefix is None else row[f"{prefix}_telegram_name"],
        is_admin=bool(row["is_admin"]) if prefix is None else bool(row[f"{prefix}_is_admin"]),
        suspended_until=row["suspended_until"]if prefix is None else row[f"{prefix}_suspended_until"],
        deleted_at=row["deleted_at"] if prefix is None else row[f"{prefix}_deleted_at"])
    return member

def _key_from_row(row: sqlite3.Row, prefix: str|None = None) -> Key:
    key = Key(
        key_id=row["key_id"] if prefix is None else row[f"{prefix}_key_id"],
    current_holder_id=row["current_holder_id"] if prefix is None else row[f"{prefix}_current_holder_id"],
    owner_member_id=row["owner_id"] if prefix is None else row[f"{prefix}_owner_id"],
    is_active=row["is_active"] if prefix is None else row[f"{prefix}_is_active"]
    )
    return key

FIRST_NAMES = (
    "Alex",
    "Dima",
    "Ivan",
    "Maria",
    "Nina",
    "Olga",
    "Pavel",
    "Sofia",
)
SURNAMES = (
    "Ivanov",
    "Kuznetsov",
    "Muller",
    "Petrov",
    "Schmidt",
    "Sokolov",
    "Smirnov",
    "Weber",
)

TEST_MAILBOXES = (
    {
        "telegram_user_id": 0,
        "name": "Dima's",
        "surname": "Mailbox",
        "room_number": 1001,
    },
    {
        "telegram_user_id": 1,
        "name": "Second",
        "surname": "Mailbox",
        "room_number": 3062,
    },
    {
        "telegram_user_id": 2,
        "name": "Last",
        "surname": "Mailbox",
        "room_number": 9999,
    },
)


def initialize_database(database_path):
    """Create the application database tables if they do not exist yet."""
    with database_connection(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS gym_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_user_id BIGINT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                surname TEXT NOT NULL,
                room_number INTEGER NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                telegram_name TEXT,
                is_admin INTEGER NOT NULL DEFAULT 0,
                deleted_at TIMESTAMP DEFAULT NULL,
                suspended_until TIMESTAMP DEFAULT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                current_holder_id INTEGER NOT NULL,
                owner_member_id INTEGER NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (current_holder_id) REFERENCES gym_members(id),
                FOREIGN KEY (owner_member_id) REFERENCES gym_members(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS key_holder_history (
                event_id INTEGER PRIMARY KEY,
                key_id INTEGER NOT NULL,
                holder_id INTEGER NOT NULL,
                taken_at TIMESTAMP NOT NULL,

                FOREIGN KEY (key_id) REFERENCES keys(id),
                FOREIGN KEY (holder_id) REFERENCES gym_members(id)
            )
            """
        )
#TODO rewrite this function using general function that alters table based on query
def change_key_holder(database_path, key_id, new_holder_id):
    """Change a key holder and append the change to holder history."""
    with database_connection(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")

        holder_exists = connection.execute(
            "SELECT 1 FROM gym_members WHERE id = ?",
            (new_holder_id,),
        ).fetchone()
        if not holder_exists:
            raise ValueError(f"gym member does not exist: {new_holder_id}")

        key_exists = connection.execute(
            "SELECT 1 FROM keys WHERE id = ?",
            (key_id,),
        ).fetchone()
        if not key_exists:
            raise ValueError(f"key does not exist: {key_id}")

        connection.execute(
            """
            UPDATE keys
            SET current_holder_id = ?
            WHERE id = ?
            """,
            (new_holder_id, key_id),
        )
        connection.execute(
            """
            INSERT INTO key_holder_history (key_id, holder_id, taken_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            """,
            (key_id, new_holder_id),
        )

def get_key_owner_mailbox_info(database_path, key_id) -> GymMember | None:
    query = """
        SELECT
            gm.id AS member_id,
            gm.telegram_user_id,
            gm.name,
            gm.surname,
            gm.room_number,
            gm.telegram_name,
            gm.is_admin,
            gm.suspended_until,
            gm.deleted_at
        FROM keys
        JOIN gym_members gm
            ON keys.owner_member_id = gm.id
        WHERE keys.id = ?
    """
    with database_connection(database_path) as connection:
        connection.row_factory = sqlite3.Row
        owner = connection.execute(query, [key_id]).fetchone()

    if owner is None:
        return None

    return _gym_member_from_row(owner)

def get_key_return_instruction_info(database_path, telegram_user_id):
    query = """
        SELECT keys.id, mailbox.room_number
        FROM keys
        JOIN gym_members holder
            ON keys.current_holder_id = holder.id
        JOIN gym_members mailbox
            ON keys.owner_member_id = mailbox.id
        WHERE holder.telegram_user_id = ?
        ORDER BY keys.id
        LIMIT 1
    """
    with database_connection(database_path) as connection:
        return connection.execute(query, [telegram_user_id]).fetchone()
#TODO use KeyHistoryRecord here, KeyHolder is just its subset
def get_current_keyholder_info(database_path,key_id,telegram_user_id=None,gym_member_id=None
                               ) -> KeyHolder | None:
    """Return the current holder details for a key, or None if the key is missing."""
    query = """
        SELECT
            keys.id AS key_id,
            gym_members.id AS member_id,
            gym_members.telegram_user_id,
            gym_members.name,
            gym_members.surname,
            gym_members.room_number,
            gym_members.telegram_name,
            gym_members.is_admin,
            gym_members.suspended_until,
            gym_members.deleted_at
        FROM keys
        JOIN gym_members ON gym_members.id = keys.current_holder_id
        WHERE keys.id = ?
    """
    parameters = [key_id]

    if telegram_user_id is not None:
        query += " AND gym_members.telegram_user_id = ?"
        parameters.append(telegram_user_id)

    if gym_member_id is not None:
        query += " AND gym_members.id = ?"
        parameters.append(gym_member_id)

    with database_connection(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.row_factory = sqlite3.Row
        holder = connection.execute(query, parameters).fetchone()

    if holder is None:
        return None

    return KeyHolder(
        key_id=holder["key_id"],
        member=_gym_member_from_row(holder))

#TODO This function does almost the same as get-key_return_instruction_info. They could be combined into single fuction. 
# Think about it
def get_key_id_by_telegram_user_id(database_path, telegram_user_id):
    """Return the first key id currently held by a Telegram user, or None."""
    query = """
        SELECT keys.id
        FROM keys
        JOIN gym_members
            ON keys.current_holder_id = gym_members.id
        WHERE gym_members.telegram_user_id = ?
    """
    with database_connection(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        key = connection.execute(query, [telegram_user_id]).fetchone()
    if key is None:
        return None
    return key[0]

def get_all_current_keyholders_info(database_path,telegram_user_id=None,gym_member_id=None
                                    ) -> list[KeyHolder]:
    """Return current holder details for all active keys."""
    query = """
        SELECT
            keys.id AS key_id,
            keys.is_active as is_active,
            gym_members.id AS member_id,
            gym_members.telegram_user_id,
            gym_members.name,
            gym_members.surname,
            gym_members.room_number,
            gym_members.telegram_name,
            gym_members.is_admin,
            gym_members.suspended_until,
            gym_members.deleted_at
        FROM keys
        JOIN gym_members ON gym_members.id = keys.current_holder_id
    """
    conditions = ["keys.is_active = ?"]
    parameters = [True]

    if telegram_user_id is not None:
        conditions.append("gym_members.telegram_user_id = ?")
        parameters.append(telegram_user_id)

    if gym_member_id is not None:
        conditions.append("gym_members.id = ?")
        parameters.append(gym_member_id)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY keys.id"

    with database_connection(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.row_factory = sqlite3.Row
        holders = connection.execute(query, parameters).fetchall()

    return [
        KeyHolder(
            key_id=holder["key_id"],
            member=_gym_member_from_row(holder),
        )
        for holder in holders
    ]


def get_active_keys(database_path)-> list[Key]:
    """Return active keys."""
    return query_key_table(database_path,Key(is_active=True))

#TODO update this code
def get_key_status(database_path, key_id: int) -> tuple[Key,GymMember,GymMember] | tuple[None,None,None]:
    """Return complete status information as a triple (key,current holder,owner) or None if key is not found"""
    query = """
        SELECT
            keys.id AS key_id,
            keys.is_active,
            holder.id AS holder_member_id,
            holder.telegram_user_id AS holder_telegram_user_id,
            holder.name AS holder_name,
            holder.surname AS holder_surname,
            holder.room_number AS holder_room_number,
            holder.telegram_name AS holder_telegram_name,
            holder.is_admin AS holder_is_admin,
            holder.suspended_until AS holder_suspended_until,
            holder.deleted_at AS holder_deleted_at,
            owner.id AS owner_member_id,
            owner.telegram_user_id AS owner_telegram_user_id,
            owner.name AS owner_name,
            owner.surname AS owner_surname,
            owner.room_number AS owner_room_number,
            owner.telegram_name AS owner_telegram_name,
            owner.is_admin AS owner_is_admin,
            owner.suspended_until AS owner_suspended_until,
            owner.deleted_at AS owner_deleted_at
        FROM keys
        JOIN gym_members holder ON holder.id = keys.current_holder_id
        JOIN gym_members owner ON owner.id = keys.owner_member_id
        WHERE keys.id = ?
    """
    with database_connection(database_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(query, (key_id,)).fetchone()

    if row is None:
        return (None,None,None)

    key = Key(
        key_id=row["key_id"],
        current_holder_id=row["holder_member_id"],
        owner_member_id=row["owner_member_id"],
        is_active=bool(row["is_active"]))
    holder = _gym_member_from_row(row,"holder")
    owner = _gym_member_from_row(row,"owner")
    return (key,holder,owner)

#TODO rewrite this function using general function that alters table based on query
def set_key_owner(database_path, key_id: int, owner_member_id: int) -> bool:
    """Set a key's owner and return whether the key exists."""
    with database_connection(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        cursor = connection.execute(
            """
            UPDATE keys
            SET owner_member_id = ?
            WHERE id = ?
            """,
            (owner_member_id, key_id),
        )
    return cursor.rowcount > 0

#TODO rewrite this function using general function that alters table based on query
def set_key_active(database_path, key_id: int, do_activate: bool) -> bool:
    """Set a key's active status and return whether the key exists."""
    with database_connection(database_path) as connection:
        cursor = connection.execute(
            """
            UPDATE keys
            SET is_active = ?
            WHERE id = ?
            """,
            (int(do_activate), key_id),
        )
    return cursor.rowcount > 0


def get_key_history(
    database_path,
    key_id: int,
    limit: int = 5,
) -> list[KeyHistoryRecord]:
    """Return the most recent holder changes for one key."""
    if limit <= 0:
        raise ValueError("limit must be positive")
    if key_id <= 0:
        raise ValueError("key_id must be positive")

    query = """
        SELECT
            history.event_id,
            history.key_id,
            history.taken_at,
            members.id AS member_id,
            members.telegram_user_id,
            members.name,
            members.surname,
            members.room_number,
            members.telegram_name,
            members.is_admin,
            members.suspended_until,
            members.deleted_at
        FROM key_holder_history history
        JOIN gym_members members ON members.id = history.holder_id
        WHERE history.key_id = ?
        ORDER BY history.taken_at DESC, history.event_id DESC
        LIMIT ?
    """

    with database_connection(database_path) as connection:
        connection.row_factory = sqlite3.Row
        records = connection.execute(query, (key_id, limit)).fetchall()

    return [
        KeyHistoryRecord(
            event_id=record["event_id"],
            key_id=record["key_id"],
            member=_gym_member_from_row(record),
            taken_at=datetime.fromisoformat(record["taken_at"]),
        )
        for record in records
    ]

def get_gym_member_id_by_telegram_user_id(database_path, telegram_user_id):
    """Return the gym member id for a Telegram user, or None if absent."""
    member = get_gym_member_by_telegram_user_id(database_path, telegram_user_id)
    if member is None:
        return None
    return member.id

def get_gym_member_by_telegram_user_id(database_path,telegram_user_id) -> GymMember | None:
    """
    Return the registered gym member for a Telegram user, or None if absent."""
    if telegram_user_id is not None:
        members = query_gym_member_records(database_path,GymMember(telegram_user_id=telegram_user_id))
        if members:
            return members[0]
    return None

def query_gym_member_records(database_path,querried_member:GymMember) -> list[GymMember]:
    """Return gym members matching the supplied filters."""
    query = """
        SELECT
            id AS member_id,
            telegram_user_id,
            name,
            surname,
            room_number,
            telegram_name,
            is_admin,
            suspended_until,
            deleted_at
        FROM gym_members
    """
    #TODO make internal function what does this loop
    conditions = []
    parameters = []
    for k,v in vars(querried_member).items():
        if v is not None:
            condition = f"{k} = ?"
            if isinstance(v,str):
                condition+=" COLLATE NOCASE"
            conditions.append(condition)
            parameters.append(v)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY surname COLLATE NOCASE, name COLLATE NOCASE, id"

    with database_connection(database_path) as connection:
        connection.row_factory = sqlite3.Row
        fetched_members = connection.execute(query, parameters).fetchall()

    return [_gym_member_from_row(member) for member in fetched_members]

def query_key_table(database_path,querried_key:Key) -> list[Key]:
    query = """
    SELECT
       id as key_id,
       current_holder_id as current_holder_id,
       owner_member_id as owner_id,
       is_active as is_active
    FROM keys
    """
    #TODO make internal function what does this loop
    conditions = []
    parameters = []
    for k,v in vars(querried_key).items():
        if v is not None:
            condition = f"{k} = ?"
            conditions.append(condition)
            parameters.append(v)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    with database_connection(database_path) as connection:
        connection.row_factory = sqlite3.Row
        fetched_keys = connection.execute(query, parameters).fetchall()
    return [_key_from_row(key) for key in fetched_keys]

def update_gym_member(database_path,member:GymMember) -> list[GymMember]:
    """Update supplied fields and return the updated gym member in a list"""
    if member.id is not None:
        raise ValueError("Member id must not be changed!")
    fields = []
    parameters = []
    for k,v in vars(member).items():
        if v is not None:
            if k == "telegram_user_id":
                telegram_user_id = v
            else:
                fields.append(k)
                parameters.append(v)
    if fields and telegram_user_id is not None:
        assignments = ", ".join(f"{field} = ?" for field in fields)
        parameters.append(telegram_user_id)
        with database_connection(database_path) as connection:
            connection.execute(
                f"""
                UPDATE gym_members
                SET {assignments}
                WHERE telegram_user_id = ?
                """,
                parameters)
    return query_gym_member_records(database_path,member)

def add_gym_member(
    database_path,new_user:GymMember) -> None:
    """Create and return a gym member."""
    try:
        with database_connection(database_path) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(
                """
                INSERT INTO gym_members (
                    telegram_user_id,
                    name,
                    surname,
                    room_number,
                    telegram_name
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    new_user.telegram_user_id,
                    new_user.name,
                    new_user.surname,
                    new_user.room_number,
                    new_user.telegram_name,
                ),
            )
    except sqlite3.IntegrityError as error:
        if get_gym_member_by_telegram_user_id(database_path, new_user.telegram_user_id):
            raise GymMemberAlreadyExistsError(
                f"gym member already exists for Telegram ID: {new_user.telegram_user_id}"
            ) from error
        else:
            raise
        
def set_admin(database_path, telegram_user_id: int, is_admin: bool) -> list[GymMember]:
    """Set admin rights and return whether the member exists."""
    return update_gym_member(database_path,
        GymMember(telegram_user_id=telegram_user_id,is_admin=is_admin))

def populate_members_table_with_mock_data(database_path,n_members,rng=None):
    """Populate the members table with random plausible mock members."""
    if n_members < 0:
        raise ValueError("n_members must not be negative")

    rng = rng or random.Random()
    inserted_member_ids = []
    used_telegram_user_ids = set()

    with database_connection(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")

        existing_telegram_user_ids = {
            row[0]
            for row in connection.execute(
                """
                SELECT telegram_user_id
                FROM gym_members
                WHERE telegram_user_id IS NOT NULL
                """
            )
        }
        used_telegram_user_ids.update(existing_telegram_user_ids)

        for _ in range(n_members):
            telegram_user_id = _generate_unique_telegram_user_id(
                rng,
                used_telegram_user_ids,
            )
            name = rng.choice(FIRST_NAMES)
            cursor = connection.execute(
                """
                INSERT INTO gym_members (
                    telegram_user_id,
                    name,
                    surname,
                    room_number,
                    telegram_name
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    telegram_user_id,
                    name,
                    rng.choice(SURNAMES),
                    rng.randint(1000, 9999),
                    f"@{name.lower()}{telegram_user_id % 10000}",
                ),
            )
            inserted_member_ids.append(cursor.lastrowid)

    return inserted_member_ids


def populate_test_mailboxes_and_keys(database_path):
    """Populate deterministic mailbox members and one key per mailbox."""
    mailbox_member_ids = []
    key_ids = []

    with database_connection(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")

        for mailbox in TEST_MAILBOXES:
            existing_mailbox = connection.execute(
                """
                SELECT id
                FROM gym_members
                WHERE telegram_user_id = ?
                """,
                (mailbox["telegram_user_id"],),
            ).fetchone()

            if existing_mailbox is None:
                mailbox_member_id = connection.execute(
                    """
                    INSERT INTO gym_members (
                        telegram_user_id,
                        name,
                        surname,
                        room_number
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        mailbox["telegram_user_id"],
                        mailbox["name"],
                        mailbox["surname"],
                        mailbox["room_number"],
                    ),
                ).lastrowid
            else:
                mailbox_member_id = existing_mailbox[0]

            mailbox_member_ids.append(mailbox_member_id)

            existing_key = connection.execute(
                """
                SELECT id
                FROM keys
                WHERE owner_member_id = ?
                ORDER BY id
                LIMIT 1
                """,
                (mailbox_member_id,),
            ).fetchone()

            if existing_key is None:
                key_id = connection.execute(
                    """
                    INSERT INTO keys (current_holder_id, owner_member_id)
                    VALUES (?, ?)
                    """,
                    (mailbox_member_id, mailbox_member_id),
                ).lastrowid
            else:
                key_id = existing_key[0]

            key_ids.append(key_id)

    return mailbox_member_ids, key_ids


def _generate_unique_telegram_user_id(rng, used_telegram_user_ids):
    while True:
        telegram_user_id = rng.randint(100_000_000, 999_999_999)
        if telegram_user_id not in used_telegram_user_ids:
            used_telegram_user_ids.add(telegram_user_id)
            return telegram_user_id


if __name__ == "__main__":
    initialize_database(DATABASE_PATH)
    populate_members_table_with_mock_data(DATABASE_PATH, 5,None)
    populate_test_mailboxes_and_keys(DATABASE_PATH)
