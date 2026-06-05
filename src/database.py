import random
import sqlite3
import sys
from pathlib import Path
from src.models import GymMember, KeyHolder
if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import DEFAULT_DATABASE_PATH


def _gym_member_from_row(row: sqlite3.Row) -> GymMember:
    return GymMember(
        id=row["member_id"],
        telegram_user_id=row["telegram_user_id"],
        name=row["name"],
        surname=row["surname"],
        room_number=row["room_number"],
        telegram_name=row["telegram_name"],
        phone_number=row["phone_number"],
        is_admin=bool(row["is_admin"]),
    )


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
        "telegram_user_id": -1,
        "name": "Second",
        "surname": "Mailbox",
        "room_number": 3062,
    },
    {
        "telegram_user_id": -2,
        "name": "Last",
        "surname": "Mailbox",
        "room_number": 9999,
    },
)


def initialize_database(database_path):
    """Create the application database tables if they do not exist yet."""
    with sqlite3.connect(database_path) as connection:
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
                phone_number TEXT,
                is_admin INTEGER NOT NULL DEFAULT 0
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

def change_key_holder(database_path, key_id, new_holder_id):
    """Change a key holder and append the change to holder history."""
    with sqlite3.connect(database_path) as connection:
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
            gm.phone_number,
            gm.is_admin
        FROM keys
        JOIN gym_members gm
            ON keys.owner_member_id = gm.id
        WHERE keys.id = ?
    """
    with sqlite3.connect(database_path) as connection:
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
    with sqlite3.connect(database_path) as connection:
        return connection.execute(query, [telegram_user_id]).fetchone()

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
            gym_members.phone_number,
            gym_members.is_admin
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

    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.row_factory = sqlite3.Row
        holder = connection.execute(query, parameters).fetchone()

    if holder is None:
        return None

    return KeyHolder(
        key_id=holder["key_id"],
        member=_gym_member_from_row(holder),
    )

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
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        key = connection.execute(query, [telegram_user_id]).fetchone()
    if key is None:
        return None
    return key[0]

def get_all_current_keyholders_info(database_path,telegram_user_id=None,gym_member_id=None
                                    ) -> list[KeyHolder]:
    """Return current holder details for all keys."""
    query = """
        SELECT
            keys.id AS key_id,
            gym_members.id AS member_id,
            gym_members.telegram_user_id,
            gym_members.name,
            gym_members.surname,
            gym_members.room_number,
            gym_members.telegram_name,
            gym_members.phone_number,
            gym_members.is_admin
        FROM keys
        JOIN gym_members ON gym_members.id = keys.current_holder_id
    """
    conditions = []
    parameters = []

    if telegram_user_id is not None:
        conditions.append("gym_members.telegram_user_id = ?")
        parameters.append(telegram_user_id)

    if gym_member_id is not None:
        conditions.append("gym_members.id = ?")
        parameters.append(gym_member_id)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY keys.id"

    with sqlite3.connect(database_path) as connection:
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


def get_key_count(database_path):
    """Return the number of tracked keys."""
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        row = connection.execute(
            """
            SELECT COUNT(*)
            FROM keys
            """
        ).fetchone()
    return row[0]

def get_gym_member_id_by_telegram_user_id(database_path, telegram_user_id):
    """Return the gym member id for a Telegram user, or None if absent."""
    member = get_gym_member_by_telegram_user_id(database_path, telegram_user_id)
    if member is None:
        return None
    return member.id


def get_gym_member_by_telegram_user_id(database_path,telegram_user_id
                                       ) -> GymMember | None:
    """Return the registered gym member for a Telegram user, or None if absent."""
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.row_factory = sqlite3.Row
        member = connection.execute(
            """
            SELECT
                id AS member_id,
                telegram_user_id,
                name,
                surname,
                room_number,
                telegram_name,
                phone_number,
                is_admin
            FROM gym_members
            WHERE telegram_user_id = ?
            """,
            (telegram_user_id,),
        ).fetchone()

    if member is None:
        return None

    return _gym_member_from_row(member)

def populate_members_table_with_mock_data(database_path,n_members,rng=None):
    """Populate the members table with random plausible mock members."""
    if n_members < 0:
        raise ValueError("n_members must not be negative")

    rng = rng or random.Random()
    inserted_member_ids = []
    used_telegram_user_ids = set()

    with sqlite3.connect(database_path) as connection:
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
                    telegram_name,
                    phone_number
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    telegram_user_id,
                    name,
                    rng.choice(SURNAMES),
                    rng.randint(1000, 9999),
                    f"@{name.lower()}{telegram_user_id % 10000}",
                    f"+491{rng.randint(100000000, 999999999)}",
                ),
            )
            inserted_member_ids.append(cursor.lastrowid)

    return inserted_member_ids


def populate_test_mailboxes_and_keys(database_path):
    """Populate deterministic mailbox members and one key per mailbox."""
    mailbox_member_ids = []
    key_ids = []

    with sqlite3.connect(database_path) as connection:
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
    initialize_database(DEFAULT_DATABASE_PATH)
    populate_members_table_with_mock_data(DEFAULT_DATABASE_PATH, 5,None)
    populate_test_mailboxes_and_keys(DEFAULT_DATABASE_PATH)
