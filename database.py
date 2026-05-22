import random
import sqlite3
from pathlib import Path


DEFAULT_DATABASE_PATH = Path("gym_bot.sqlite3")

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


def initialize_database(database_path=DEFAULT_DATABASE_PATH):
    """Create the application database tables if they do not exist yet."""
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS gym_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_user_id BIGINT UNIQUE,
                name TEXT,
                surname TEXT NOT NULL,
                room_number INTEGER NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                current_holder_id INTEGER NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (current_holder_id) REFERENCES gym_members(id)
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

def on_holder_change(database_path, key_id, new_holder_id):
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
    connection.close()


def get_current_key_holder(
    database_path=DEFAULT_DATABASE_PATH,
    key_id=1,
    telegram_user_id=None,
):
    """Return the current holder details for a key, or None if the key is missing."""
    query = """
        SELECT gym_members.name, gym_members.surname, gym_members.room_number
        FROM keys
        JOIN gym_members ON gym_members.id = keys.current_holder_id
        WHERE keys.id = ?
    """
    parameters = [key_id]

    if telegram_user_id is not None:
        query += " AND gym_members.telegram_user_id = ?"
        parameters.append(telegram_user_id)

    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        return connection.execute(query, parameters).fetchone()


def get_gym_member_id_by_telegram_user_id(database_path, telegram_user_id):
    """Return the gym member id for a Telegram user, or None if absent."""
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        member = connection.execute(
            """
            SELECT id
            FROM gym_members
            WHERE telegram_user_id = ?
            """,
            (telegram_user_id,),
        ).fetchone()

    if member is None:
        return None

    return member[0]


def populate_members_table_with_mock_data(
    database_path=DEFAULT_DATABASE_PATH,
    n_members=5,
    rng=None
):
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
            cursor = connection.execute(
                """
                INSERT INTO gym_members (telegram_user_id, name, surname, room_number)
                VALUES (?, ?, ?, ?)
                """,
                (
                    telegram_user_id,
                    rng.choice(FIRST_NAMES),
                    rng.choice(SURNAMES),
                    rng.randint(1000, 9999),
                ),
            )
            inserted_member_ids.append(cursor.lastrowid)
    connection.close()

    return inserted_member_ids


def _generate_unique_telegram_user_id(rng, used_telegram_user_ids):
    while True:
        telegram_user_id = rng.randint(100_000_000, 999_999_999)
        if telegram_user_id not in used_telegram_user_ids:
            used_telegram_user_ids.add(telegram_user_id)
            return telegram_user_id

if __name__ == "__main__":
    initialize_database()
    populate_members_table_with_mock_data(DEFAULT_DATABASE_PATH,5)
