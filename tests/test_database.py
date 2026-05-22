import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from database import initialize_database, on_holder_change


def create_gym_member(connection, surname, room_number):
    cursor = connection.execute(
        """
        INSERT INTO gym_members (surname, room_number)
        VALUES (?, ?)
        """,
        (surname, room_number),
    )
    return cursor.lastrowid


def create_key(connection, current_holder_id):
    cursor = connection.execute(
        """
        INSERT INTO keys (current_holder_id)
        VALUES (?)
        """,
        (current_holder_id,),
    )
    return cursor.lastrowid


class DatabaseTests(unittest.TestCase):
    def test_initialize_database_creates_application_tables(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"

            initialize_database(database_path)

            with sqlite3.connect(database_path) as connection:
                table_names = {
                    row[0]
                    for row in connection.execute(
                        """
                        SELECT name
                        FROM sqlite_master
                        WHERE type = 'table'
                        """
                    )
                }

            self.assertIn("gym_members", table_names)
            self.assertIn("keys", table_names)
            self.assertIn("key_holder_history", table_names)

    def test_initialize_database_can_run_more_than_once(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"

            initialize_database(database_path)
            initialize_database(database_path)

            with sqlite3.connect(database_path) as connection:
                gym_members_table = connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table' AND name = 'gym_members'
                    """
                ).fetchone()

            self.assertEqual(("gym_members",), gym_members_table)

    def test_keys_current_holder_references_gym_members(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"

            initialize_database(database_path)

            with sqlite3.connect(database_path) as connection:
                foreign_keys = connection.execute("PRAGMA foreign_key_list(keys)").fetchall()

            self.assertEqual("gym_members", foreign_keys[0][2])
            self.assertEqual("current_holder_id", foreign_keys[0][3])
            self.assertEqual("id", foreign_keys[0][4])

    def test_on_holder_change_updates_key_holder_and_history(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            initialize_database(database_path)

            with sqlite3.connect(database_path) as connection:
                first_holder_id = create_gym_member(connection, "Ivanov", 101)
                second_holder_id = create_gym_member(connection, "Petrov", 102)
                key_id = create_key(connection, first_holder_id)

            on_holder_change(database_path, key_id, second_holder_id)

            with sqlite3.connect(database_path) as connection:
                current_holder_id = connection.execute(
                    "SELECT current_holder_id FROM keys WHERE id = ?",
                    (key_id,),
                ).fetchone()
                history_record = connection.execute(
                    """
                    SELECT key_id, holder_id
                    FROM key_holder_history
                    WHERE key_id = ?
                    """,
                    (key_id,),
                ).fetchone()

            self.assertEqual((second_holder_id,), current_holder_id)
            self.assertEqual((key_id, second_holder_id), history_record)

    def test_on_holder_change_rejects_missing_holder(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            initialize_database(database_path)

            with sqlite3.connect(database_path) as connection:
                holder_id = create_gym_member(connection, "Ivanov", 101)
                key_id = create_key(connection, holder_id)

            with self.assertRaisesRegex(ValueError, "gym member does not exist: 999"):
                on_holder_change(database_path, key_id, 999)

    def test_on_holder_change_rejects_missing_key(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            initialize_database(database_path)

            with sqlite3.connect(database_path) as connection:
                holder_id = create_gym_member(connection, "Ivanov", 101)

            with self.assertRaisesRegex(ValueError, "key does not exist: 999"):
                on_holder_change(database_path, 999, holder_id)


if __name__ == "__main__":
    unittest.main()
