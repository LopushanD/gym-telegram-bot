import sqlite3
from pathlib import Path


DEFAULT_DATABASE_PATH = Path("gym_bot.sqlite3")


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
