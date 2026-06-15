import random
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.database import (
    GymMemberAlreadyExistsError,
    add_gym_member,
    get_all_current_keyholders_info,
    get_current_keyholder_info,
    get_gym_member_by_telegram_user_id,
    get_gym_member_id_by_telegram_user_id,
    get_gym_member_records,
    get_key_id_by_telegram_user_id,
    get_key_count,
    get_key_history,
    get_key_status,
    get_key_owner_mailbox_info,
    get_key_return_instruction_info,
    initialize_database,
    change_key_holder,
    populate_members_table_with_mock_data,
    populate_test_mailboxes_and_keys,
    set_key_active,
    update_gym_member,
)
from src.models import GymMember, KeyHolder, KeyStatus


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

    def test_get_key_history_returns_latest_records_with_member_details(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            initialize_database(database_path)

            with sqlite3.connect(database_path) as connection:
                first_holder_id = create_gym_member_with_telegram_user_id(
                    connection,
                    100,
                    "Ivanov",
                    101,
                )
                second_holder_id = create_gym_member_with_telegram_user_id(
                    connection,
                    200,
                    "Petrov",
                    102,
                )
                key_id = create_key(connection, first_holder_id)
                connection.executemany(
                    """
                    INSERT INTO key_holder_history (key_id, holder_id, taken_at)
                    VALUES (?, ?, ?)
                    """,
                    [
                        (key_id, first_holder_id, "2026-06-01 10:00:00"),
                        (key_id, second_holder_id, "2026-06-02 10:00:00"),
                    ],
                )

            records = get_key_history(database_path, key_id, limit=1)

            self.assertEqual(1, len(records))
            self.assertEqual(key_id, records[0].key_id)
            self.assertEqual(second_holder_id, records[0].member.id)
            self.assertEqual(datetime(2026, 6, 2, 10, 0), records[0].taken_at)

    def test_get_key_history_rejects_non_positive_limit(self):
        with self.assertRaises(ValueError):
            get_key_history(":memory:", key_id=1, limit=0)

    def test_get_key_history_filters_by_key_id(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            initialize_database(database_path)

            with sqlite3.connect(database_path) as connection:
                holder_id = create_gym_member_with_telegram_user_id(
                    connection,
                    100,
                    "Ivanov",
                    101,
                )
                first_key_id = create_key(connection, holder_id)
                second_key_id = create_key(connection, holder_id)
                connection.executemany(
                    """
                    INSERT INTO key_holder_history (key_id, holder_id, taken_at)
                    VALUES (?, ?, ?)
                    """,
                    [
                        (first_key_id, holder_id, "2026-06-01 10:00:00"),
                        (second_key_id, holder_id, "2026-06-02 10:00:00"),
                    ],
                )

            records = get_key_history(database_path, first_key_id)

            self.assertEqual([first_key_id], [record.key_id for record in records])

    def test_get_key_history_rejects_non_positive_key_id(self):
        with self.assertRaises(ValueError):
            get_key_history(":memory:", 0)

    def test_change_key_holder_preserves_key_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            initialize_database(database_path)

            with sqlite3.connect(database_path) as connection:
                owner_id = create_gym_member_with_telegram_user_id(
                    connection,
                    123456,
                    "Ivanov",
                    101,
                )
                new_holder_id = create_gym_member_with_telegram_user_id(
                    connection,
                    654321,
                    "Petrov",
                    102,
                )
                key_id = create_key(connection, owner_id)

            change_key_holder(database_path, key_id, new_holder_id)

            owner = get_key_owner_mailbox_info(database_path, key_id)

            self.assertEqual(
                GymMember(
                    id=owner_id,
                    telegram_user_id=123456,
                    name="Alex",
                    surname="Ivanov",
                    room_number=101,
                    telegram_name=None,
                    phone_number=None,
                    is_admin=False,
                ),
                owner,
            )

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

    def test_populate_test_mailboxes_and_keys_creates_mailboxes_and_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            initialize_database(database_path)

            mailbox_ids, key_ids = populate_test_mailboxes_and_keys(database_path)

            with sqlite3.connect(database_path) as connection:
                mailboxes = connection.execute(
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
                keys = connection.execute(
                    """
                    SELECT id, current_holder_id, owner_member_id, is_active
                    FROM keys
                    ORDER BY id
                    """
                ).fetchall()

            self.assertEqual(
                [
                    (mailbox_ids[0], 0, "Dima's", "Mailbox", 1001, None, None),
                    (mailbox_ids[1], -1, "Second", "Mailbox", 3062, None, None),
                    (mailbox_ids[2], -2, "Last", "Mailbox", 9999, None, None),
                ],
                mailboxes,
            )
            self.assertEqual(
                [
                    (key_ids[0], mailbox_ids[0], mailbox_ids[0], 1),
                    (key_ids[1], mailbox_ids[1], mailbox_ids[1], 1),
                    (key_ids[2], mailbox_ids[2], mailbox_ids[2], 1),
                ],
                keys,
            )

    def test_populate_test_mailboxes_and_keys_can_run_more_than_once(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            initialize_database(database_path)

            first_result = populate_test_mailboxes_and_keys(database_path)
            second_result = populate_test_mailboxes_and_keys(database_path)

            with sqlite3.connect(database_path) as connection:
                mailbox_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM gym_members
                    WHERE surname = 'Mailbox'
                    """
                ).fetchone()[0]
                key_count = connection.execute("SELECT COUNT(*) FROM keys").fetchone()[0]

            self.assertEqual(first_result, second_result)
            self.assertEqual(3, mailbox_count)
            self.assertEqual(3, key_count)

    def test_get_current_key_holder_returns_holder_details(self):
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

            holder = get_current_keyholder_info(database_path, key_id)

            self.assertEqual(
                KeyHolder(
                    key_id=key_id,
                    member=GymMember(
                        id=holder_id,
                        telegram_user_id=123456,
                        name="Dima",
                        surname="Ivanov",
                        room_number=1234,
                        telegram_name="@dima",
                        phone_number="+49123456789",
                        is_admin=False,
                    ),
                ),
                holder,
            )

    def test_get_all_current_keyholders_returns_key_ids_with_holder_details(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            initialize_database(database_path)

            with sqlite3.connect(database_path) as connection:
                first_holder_id = create_gym_member_with_telegram_user_id(
                    connection,
                    123456,
                    "Ivanov",
                    1234,
                    name="Dima",
                    telegram_name="@dima",
                    phone_number="+49123456789",
                )
                second_holder_id = create_gym_member_with_telegram_user_id(
                    connection,
                    654321,
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
                    KeyHolder(
                        key_id=first_key_id,
                        member=GymMember(
                            id=first_holder_id,
                            telegram_user_id=123456,
                            name="Dima",
                            surname="Ivanov",
                            room_number=1234,
                            telegram_name="@dima",
                            phone_number="+49123456789",
                            is_admin=False,
                        ),
                    ),
                    KeyHolder(
                        key_id=second_key_id,
                        member=GymMember(
                            id=second_holder_id,
                            telegram_user_id=654321,
                            name="Alex",
                            surname="Petrov",
                            room_number=4321,
                            telegram_name="@alex",
                            phone_number="+49987654321",
                            is_admin=False,
                        ),
                    ),
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

            self.assertEqual(
                KeyHolder(
                    key_id=key_id,
                    member=GymMember(
                        id=holder_id,
                        telegram_user_id=123456,
                        name="Dima",
                        surname="Ivanov",
                        room_number=1234,
                        telegram_name="@dima",
                        phone_number="+49123456789",
                        is_admin=False,
                    ),
                ),
                holder,
            )

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

    def test_get_gym_member_by_telegram_user_id_returns_registered_member_data(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            initialize_database(database_path)

            with sqlite3.connect(database_path) as connection:
                member_id = create_gym_member_with_telegram_user_id(
                    connection,
                    123456,
                    "Database Surname",
                    1234,
                    name="Database Name",
                    telegram_name="telegram_name",
                    phone_number="12345",
                )

            member = get_gym_member_by_telegram_user_id(database_path, 123456)

            self.assertEqual(member_id, member.id)
            self.assertEqual("Database Name Database Surname", member.full_name)
            self.assertEqual(1234, member.room_number)
            self.assertEqual("telegram_name", member.telegram_name)
            self.assertEqual("12345", member.phone_number)

    def test_get_gym_member_records_filters_and_returns_member_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            initialize_database(database_path)

            with sqlite3.connect(database_path) as connection:
                expected_id = create_gym_member_with_telegram_user_id(
                    connection,
                    123456,
                    "Lovelace",
                    1234,
                    name="Ada",
                    telegram_name="@ada",
                    phone_number="+49123456789",
                )
                create_gym_member_with_telegram_user_id(
                    connection,
                    654321,
                    "Byron",
                    4321,
                    name="Ada",
                )

            members = get_gym_member_records(
                database_path,
                name="ada",
                surname="lovelace",
                room_number=1234,
            )

            self.assertEqual(1, len(members))
            member = members[0]
            self.assertEqual(expected_id, member.id)
            self.assertEqual(123456, member.telegram_user_id)
            self.assertEqual("Ada", member.name)
            self.assertEqual("Lovelace", member.surname)
            self.assertEqual(1234, member.room_number)
            self.assertEqual("@ada", member.telegram_name)
            self.assertEqual("+49123456789", member.phone_number)
            self.assertFalse(member.is_admin)

    def test_add_gym_member_creates_member_with_optional_contact_data(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            initialize_database(database_path)

            member = add_gym_member(
                database_path,
                telegram_user_id=123456,
                name="Database",
                surname="Member",
                room_number=1234,
                telegram_name="@database_member",
                phone_number="+49123456789",
            )

            self.assertEqual(123456, member.telegram_user_id)
            self.assertEqual("Database Member", member.full_name)
            self.assertEqual(1234, member.room_number)
            self.assertEqual("@database_member", member.telegram_name)
            self.assertEqual("+49123456789", member.phone_number)
            self.assertFalse(member.is_admin)

    def test_add_gym_member_allows_missing_optional_contact_data(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            initialize_database(database_path)

            member = add_gym_member(
                database_path,
                telegram_user_id=123456,
                name="Database",
                surname="Member",
                room_number=1234,
            )

            self.assertIsNone(member.telegram_name)
            self.assertIsNone(member.phone_number)

    def test_add_gym_member_rejects_duplicate_telegram_user_id(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            initialize_database(database_path)
            add_gym_member(
                database_path,
                telegram_user_id=123456,
                name="First",
                surname="Member",
                room_number=1234,
            )

            with self.assertRaisesRegex(
                GymMemberAlreadyExistsError,
                "gym member already exists for Telegram ID: 123456",
            ):
                add_gym_member(
                    database_path,
                    telegram_user_id=123456,
                    name="Second",
                    surname="Member",
                    room_number=5678,
                )

    def test_update_gym_member_updates_only_supplied_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            initialize_database(database_path)
            add_gym_member(
                database_path,
                telegram_user_id=123456,
                name="Old",
                surname="Surname",
                room_number=1234,
                telegram_name="@old",
                phone_number="+49111",
            )

            member = update_gym_member(
                database_path,
                123456,
                name="New",
                room_number=4321,
            )

            self.assertEqual("New", member.name)
            self.assertEqual("Surname", member.surname)
            self.assertEqual(4321, member.room_number)
            self.assertEqual("@old", member.telegram_name)
            self.assertEqual("+49111", member.phone_number)

    def test_update_gym_member_returns_none_when_member_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            initialize_database(database_path)

            member = update_gym_member(database_path, 123456, name="New")

            self.assertIsNone(member)

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

    def test_get_key_status_returns_holder_owner_and_active_status(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            initialize_database(database_path)

            with sqlite3.connect(database_path) as connection:
                owner_id = create_gym_member_with_telegram_user_id(
                    connection,
                    100,
                    "Mailbox",
                    1234,
                    name="Key",
                )
                holder_id = create_gym_member_with_telegram_user_id(
                    connection,
                    200,
                    "Holder",
                    5678,
                    name="Current",
                )
                key_id = create_key(connection, holder_id, owner_id)
                connection.execute(
                    "UPDATE keys SET is_active = 0 WHERE id = ?",
                    (key_id,),
                )

            self.assertEqual(
                KeyStatus(
                    key_id=key_id,
                    current_holder=GymMember(
                        holder_id, 200, "Current", "Holder", 5678, None, None, False
                    ),
                    owner=GymMember(
                        owner_id, 100, "Key", "Mailbox", 1234, None, None, False
                    ),
                    is_active=False,
                ),
                get_key_status(database_path, key_id),
            )

    def test_get_key_status_returns_none_for_missing_key(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            initialize_database(database_path)

            self.assertIsNone(get_key_status(database_path, 999))

    def test_set_key_active_updates_status(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            initialize_database(database_path)

            with sqlite3.connect(database_path) as connection:
                holder_id = create_gym_member_with_telegram_user_id(
                    connection,
                    123456,
                    "Holder",
                    1234,
                )
                key_id = create_key(connection, holder_id)

            self.assertTrue(set_key_active(database_path, key_id, False))
            self.assertFalse(get_key_status(database_path, key_id).is_active)
            self.assertTrue(set_key_active(database_path, key_id, True))
            self.assertTrue(get_key_status(database_path, key_id).is_active)

    def test_set_key_active_returns_false_for_missing_key(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            initialize_database(database_path)

            self.assertFalse(set_key_active(database_path, 999, True))


if __name__ == "__main__":
    unittest.main()
