import sqlite3
import tempfile
import unittest
from pathlib import Path

from src.command_handlers_utility import (
    UpdateUserUsageError,
    parse_update_user_command_arguments,
    process_gym_member_records,
)
from src.database import (
    add_gym_member,
    get_gym_member_by_telegram_user_id,
    initialize_database,
)
from src.models import GymMember


class RegistrationDatabaseFieldTests(unittest.TestCase):
    def test_fresh_database_has_telegram_name_and_no_phone_column(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"

            initialize_database(database_path)

            with sqlite3.connect(database_path) as connection:
                columns = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(gym_members)")
                }

            self.assertIn("telegram_name", columns)
            self.assertNotIn("phone_number", columns)

    def test_initialization_discards_legacy_phone_data_and_preserves_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            with sqlite3.connect(database_path) as connection:
                connection.executescript(
                    """
                    CREATE TABLE gym_members (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        telegram_user_id BIGINT UNIQUE NOT NULL,
                        name TEXT NOT NULL,
                        surname TEXT NOT NULL,
                        room_number INTEGER NOT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        telegram_name TEXT,
                        phone_number TEXT,
                        is_admin INTEGER NOT NULL DEFAULT 0
                    );
                    INSERT INTO gym_members (
                        telegram_user_id, name, surname, room_number,
                        telegram_name, phone_number
                    ) VALUES (123, 'Ada', 'Lovelace', 1204, '@ada', '+49123');
                    CREATE TABLE keys (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        current_holder_id INTEGER NOT NULL,
                        owner_member_id INTEGER NOT NULL,
                        is_active INTEGER NOT NULL DEFAULT 1,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (current_holder_id) REFERENCES gym_members(id),
                        FOREIGN KEY (owner_member_id) REFERENCES gym_members(id)
                    );
                    INSERT INTO keys (current_holder_id, owner_member_id)
                    VALUES (1, 1);
                    """
                )

            initialize_database(database_path)

            with sqlite3.connect(database_path) as connection:
                columns = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(gym_members)")
                }
                key_members = connection.execute(
                    "SELECT current_holder_id, owner_member_id FROM keys WHERE id = 1"
                ).fetchone()
                foreign_key_errors = connection.execute(
                    "PRAGMA foreign_key_check"
                ).fetchall()

            self.assertNotIn("phone_number", columns)
            self.assertEqual((1, 1), key_members)
            self.assertEqual([], foreign_key_errors)

    def test_add_gym_member_requires_non_empty_telegram_name(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            initialize_database(database_path)

            for telegram_name in (None, "", "   "):
                with self.subTest(telegram_name=telegram_name):
                    with self.assertRaisesRegex(
                        ValueError,
                        "telegram name is required",
                    ):
                        add_gym_member(
                            database_path,
                            telegram_user_id=123,
                            name="Ada",
                            surname="Lovelace",
                            room_number=1204,
                            telegram_name=telegram_name,
                        )

            member = add_gym_member(
                database_path,
                telegram_user_id=123,
                name="Ada",
                surname="Lovelace",
                room_number=1204,
                telegram_name="@ada",
            )

            self.assertEqual("@ada", member.telegram_name)
            self.assertFalse(hasattr(member, "phone_number"))
            self.assertEqual(
                member,
                get_gym_member_by_telegram_user_id(database_path, 123),
            )


class RegistrationCommandFieldTests(unittest.TestCase):
    def test_phone_update_option_is_rejected(self):
        with self.assertRaises(UpdateUserUsageError):
            parse_update_user_command_arguments(
                ["123", "--phone-number", "+49123"]
            )

    def test_member_output_contains_telegram_name_and_no_phone(self):
        member = GymMember(1, 123, "Ada", "Lovelace", 1204, "@ada", False)
        member_text = process_gym_member_records(
            [member],
            "\n---\n",
        )[0]

        self.assertIn("Telegram username: @ada", member_text)
        self.assertNotIn("Phone", member_text)
