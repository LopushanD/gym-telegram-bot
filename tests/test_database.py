import random
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from database import initialize_database, on_holder_change, populate_members_table_with_mock_data


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

    def test_populate_members_table_with_mock_data_creates_requested_members(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            initialize_database(database_path)
            member_ids = populate_members_table_with_mock_data(
                database_path,
                n_members=7,
                rng=random.Random(1),
            )

            with sqlite3.connect(database_path) as connection:
                members = connection.execute(
                    """
                    SELECT id, telegram_user_id, name, surname, room_number
                    FROM gym_members
                    ORDER BY id
                    """
                ).fetchall()

            self.assertEqual(7, len(member_ids))
            self.assertEqual(7, len(members))
            self.assertEqual(member_ids, [member[0] for member in members])
            self.assertEqual(
                7,
                len({member[1] for member in members}),
            )
            for _, telegram_user_id, name, surname, room_number in members:
                self.assertIsInstance(telegram_user_id, int)
                self.assertTrue(name)
                self.assertTrue(surname)
                self.assertGreaterEqual(room_number, 1000)
                self.assertLessEqual(room_number, 9999)

    def test_populate_members_table_with_mock_data_rejects_negative_member_count(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"

            with self.assertRaisesRegex(ValueError, "n_members must not be negative"):
                initialize_database(database_path)
                populate_members_table_with_mock_data(database_path, n_members=-1)


if __name__ == "__main__":
    unittest.main()
