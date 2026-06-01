import random
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.database import (
    get_all_current_keyholders_info,
    get_current_keyholder_info,
    get_gym_member_id_by_telegram_user_id,
    get_key_id_by_telegram_user_id,
    get_key_count,
    get_key_owner_mailbox_info,
    get_key_return_instruction_info,
    initialize_database,
    change_key_holder,
    populate_members_table_with_mock_data,
)


def create_gym_member(
    connection,
    surname,
    room_number,
    name="Alex",
    telegram_name=None,
    phone_number=None,
):
    cursor = connection.execute(
        """
        INSERT INTO gym_members (name, surname, room_number, telegram_name, phone_number)
        VALUES (?, ?, ?, ?, ?)
        """,
        (name, surname, room_number, telegram_name, phone_number),
    )
    return cursor.lastrowid


def create_gym_member_with_telegram_user_id(
    connection,
    telegram_user_id,
    surname,
    room_number,
    name="Alex",
    telegram_name=None,
    phone_number=None,
):
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
        (telegram_user_id, name, surname, room_number, telegram_name, phone_number),
    )
    return cursor.lastrowid


def create_key(connection, current_holder_id, owner_member_id=None):
    if owner_member_id is None:
        owner_member_id = current_holder_id

    cursor = connection.execute(
        """
        INSERT INTO keys (current_holder_id, owner_member_id)
        VALUES (?, ?)
        """,
        (current_holder_id, owner_member_id),
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

    def test_initialize_database_creates_gym_member_contact_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"

            initialize_database(database_path)

            with sqlite3.connect(database_path) as connection:
                column_names = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(gym_members)")
                }

            self.assertIn("telegram_name", column_names)
            self.assertIn("phone_number", column_names)

    def test_initialize_database_adds_contact_columns_to_existing_members_table(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"

            with sqlite3.connect(database_path) as connection:
                connection.execute(
                    """
                    CREATE TABLE gym_members (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        telegram_user_id BIGINT UNIQUE,
                        name TEXT,
                        surname TEXT NOT NULL,
                        room_number INTEGER NOT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )

            initialize_database(database_path)

            with sqlite3.connect(database_path) as connection:
                column_names = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(gym_members)")
                }

            self.assertIn("telegram_name", column_names)
            self.assertIn("phone_number", column_names)

    def test_keys_members_reference_gym_members(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"

            initialize_database(database_path)

            with sqlite3.connect(database_path) as connection:
                foreign_keys = connection.execute("PRAGMA foreign_key_list(keys)").fetchall()

            referenced_columns = {
                foreign_key[3]: (foreign_key[2], foreign_key[4])
                for foreign_key in foreign_keys
            }
            self.assertEqual(
                ("gym_members", "id"),
                referenced_columns["current_holder_id"],
            )
            self.assertEqual(
                ("gym_members", "id"),
                referenced_columns["owner_member_id"],
            )

    def test_initialize_database_adds_key_owner_to_existing_keys_table(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"

            with sqlite3.connect(database_path) as connection:
                connection.execute(
                    """
                    CREATE TABLE gym_members (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        telegram_user_id BIGINT UNIQUE,
                        name TEXT,
                        surname TEXT NOT NULL,
                        room_number INTEGER NOT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        telegram_name TEXT,
                        phone_number TEXT
                    )
                    """
                )
                holder_id = create_gym_member(connection, "Ivanov", 101)
                connection.execute(
                    """
                    CREATE TABLE keys (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        current_holder_id INTEGER NOT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (current_holder_id) REFERENCES gym_members(id)
                    )
                    """
                )
                key_id = connection.execute(
                    """
                    INSERT INTO keys (current_holder_id)
                    VALUES (?)
                    """,
                    (holder_id,),
                ).lastrowid

            initialize_database(database_path)

            with sqlite3.connect(database_path) as connection:
                key_owner = connection.execute(
                    """
                    SELECT owner_member_id
                    FROM keys
                    WHERE id = ?
                    """,
                    (key_id,),
                ).fetchone()

            self.assertEqual((holder_id,), key_owner)

    def test_get_key_count_returns_total_number_of_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            initialize_database(database_path)

            with sqlite3.connect(database_path) as connection:
                first_holder_id = create_gym_member(connection, "Ivanov", 101)
                second_holder_id = create_gym_member(connection, "Petrov", 102)
                create_key(connection, first_holder_id)
                create_key(connection, second_holder_id)

            self.assertEqual(2, get_key_count(database_path))

    def test_change_key_holder_updates_key_holder_and_history(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            initialize_database(database_path)

            with sqlite3.connect(database_path) as connection:
                first_holder_id = create_gym_member(connection, "Ivanov", 101)
                second_holder_id = create_gym_member(connection, "Petrov", 102)
                key_id = create_key(connection, first_holder_id)

            change_key_holder(database_path, key_id, second_holder_id)

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

    def test_change_key_holder_preserves_key_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            initialize_database(database_path)

            with sqlite3.connect(database_path) as connection:
                owner_id = create_gym_member(connection, "Ivanov", 101)
                new_holder_id = create_gym_member(connection, "Petrov", 102)
                key_id = create_key(connection, owner_id)

            change_key_holder(database_path, key_id, new_holder_id)

            owner = get_key_owner_mailbox_info(database_path, key_id)

            self.assertEqual((owner_id, 101), owner)

    def test_change_key_holder_rejects_missing_holder(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            initialize_database(database_path)

            with sqlite3.connect(database_path) as connection:
                holder_id = create_gym_member(connection, "Ivanov", 101)
                key_id = create_key(connection, holder_id)

            with self.assertRaisesRegex(ValueError, "gym member does not exist: 999"):
                change_key_holder(database_path, key_id, 999)

    def test_change_key_holder_rejects_missing_key(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            initialize_database(database_path)

            with sqlite3.connect(database_path) as connection:
                holder_id = create_gym_member(connection, "Ivanov", 101)

            with self.assertRaisesRegex(ValueError, "key does not exist: 999"):
                change_key_holder(database_path, 999, holder_id)

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
                    SELECT
                        id,
                        telegram_user_id,
                        name,
                        surname,
                        room_number,
                        telegram_name,
                        phone_number
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
            for (
                _,
                telegram_user_id,
                name,
                surname,
                room_number,
                telegram_name,
                phone_number,
            ) in members:
                self.assertIsInstance(telegram_user_id, int)
                self.assertTrue(name)
                self.assertTrue(surname)
                self.assertGreaterEqual(room_number, 1000)
                self.assertLessEqual(room_number, 9999)
                self.assertTrue(telegram_name.startswith("@"))
                self.assertTrue(phone_number.startswith("+491"))

    def test_populate_members_table_with_mock_data_rejects_negative_member_count(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"

            with self.assertRaisesRegex(ValueError, "n_members must not be negative"):
                initialize_database(database_path)
                populate_members_table_with_mock_data(database_path, n_members=-1)

    def test_get_current_key_holder_returns_holder_details(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            initialize_database(database_path)

            with sqlite3.connect(database_path) as connection:
                holder_id = create_gym_member(
                    connection,
                    "Ivanov",
                    1234,
                    name="Dima",
                    telegram_name="@dima",
                    phone_number="+49123456789",
                )
                key_id = create_key(connection, holder_id)

            holder = get_current_keyholder_info(database_path, key_id)

            self.assertEqual((key_id, "Dima", "Ivanov", 1234, "@dima", "+49123456789"), holder)

    def test_get_all_current_keyholders_returns_key_ids_with_holder_details(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            initialize_database(database_path)

            with sqlite3.connect(database_path) as connection:
                first_holder_id = create_gym_member(
                    connection,
                    "Ivanov",
                    1234,
                    name="Dima",
                    telegram_name="@dima",
                    phone_number="+49123456789",
                )
                second_holder_id = create_gym_member(
                    connection,
                    "Petrov",
                    4321,
                    name="Alex",
                    telegram_name="@alex",
                    phone_number="+49987654321",
                )
                first_key_id = create_key(connection, first_holder_id)
                second_key_id = create_key(connection, second_holder_id)

            holders = get_all_current_keyholders_info(database_path)

            self.assertEqual(
                [
                    (first_key_id, "Dima", "Ivanov", 1234, "@dima", "+49123456789"),
                    (second_key_id, "Alex", "Petrov", 4321, "@alex", "+49987654321"),
                ],
                holders,
            )

    def test_get_current_key_holder_returns_none_for_missing_key(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            initialize_database(database_path)

            holder = get_current_keyholder_info(database_path, key_id=999)

            self.assertIsNone(holder)

    def test_get_current_key_holder_can_filter_by_telegram_user_id(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            initialize_database(database_path)

            with sqlite3.connect(database_path) as connection:
                holder_id = create_gym_member_with_telegram_user_id(
                    connection,
                    123456,
                    "Ivanov",
                    1234,
                    name="Dima",
                    telegram_name="@dima",
                    phone_number="+49123456789",
                )
                key_id = create_key(connection, holder_id)

            holder = get_current_keyholder_info(
                database_path,
                key_id,
                telegram_user_id=123456,
            )

            self.assertEqual((key_id, "Dima", "Ivanov", 1234, "@dima", "+49123456789"), holder)

    def test_get_current_key_holder_returns_none_when_telegram_user_is_not_holder(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            initialize_database(database_path)

            with sqlite3.connect(database_path) as connection:
                holder_id = create_gym_member_with_telegram_user_id(
                    connection,
                    123456,
                    "Ivanov",
                    1234,
                )
                key_id = create_key(connection, holder_id)

            holder = get_current_keyholder_info(
                database_path,
                key_id=key_id,
                telegram_user_id=654321,
            )

            self.assertIsNone(holder)

    def test_get_gym_member_id_by_telegram_user_id_returns_member_id(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            initialize_database(database_path)

            with sqlite3.connect(database_path) as connection:
                member_id = create_gym_member_with_telegram_user_id(
                    connection,
                    123456,
                    "Ivanov",
                    1234,
                )

            found_member_id = get_gym_member_id_by_telegram_user_id(
                database_path,
                123456,
            )

            self.assertEqual(member_id, found_member_id)

    def test_get_gym_member_id_by_telegram_user_id_returns_none_when_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            initialize_database(database_path)

            member_id = get_gym_member_id_by_telegram_user_id(
                database_path,
                123456,
            )

            self.assertIsNone(member_id)

    def test_get_key_id_by_telegram_user_id_returns_currently_held_key_id(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            initialize_database(database_path)

            with sqlite3.connect(database_path) as connection:
                holder_id = create_gym_member_with_telegram_user_id(
                    connection,
                    123456,
                    "Ivanov",
                    1234,
                )
                key_id = create_key(connection, holder_id)

            found_key_id = get_key_id_by_telegram_user_id(
                database_path,
                123456,
            )

            self.assertEqual(key_id, found_key_id)

    def test_get_key_id_by_telegram_user_id_returns_none_when_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            initialize_database(database_path)

            key_id = get_key_id_by_telegram_user_id(
                database_path,
                123456,
            )

            self.assertIsNone(key_id)

    def test_get_key_return_instruction_uses_owner_mailbox_room(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            initialize_database(database_path)

            with sqlite3.connect(database_path) as connection:
                owner_id = create_gym_member(connection, "Owner", 1234)
                holder_id = create_gym_member_with_telegram_user_id(
                    connection,
                    123456,
                    "Holder",
                    5678,
                )
                key_id = create_key(
                    connection,
                    current_holder_id=holder_id,
                    owner_member_id=owner_id,
                )

            instruction = get_key_return_instruction_info(database_path, 123456)

            self.assertEqual((key_id, 1234), instruction)


if __name__ == "__main__":
    unittest.main()
