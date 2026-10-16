import sqlite3
import tempfile
import unittest
from pathlib import Path

from src.database import (
    database_connection,
    initialize_database,
    query_key_table,
    update_key_table,
)
from src.models import Key


class UpdateKeyTableTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.path = Path(directory) / "keys.sqlite3"
        initialize_database(self.path)
        with database_connection(self.path) as connection:
            connection.executemany(
                """INSERT INTO gym_members (id, telegram_user_id, name, surname, room_number)
                   VALUES (?, ?, ?, ?, ?)""",
                [(10, 100, "Ada", "Owner", 101), (20, 200, "Alex", "Holder", 202)],
            )
            connection.executemany(
                """INSERT INTO keys (id, current_holder_id, owner_member_id, name, is_in_mailbox)
                   VALUES (?, ?, ?, ?, ?)""",
                [(7, 10, 10, "Red", 1), (8, 20, 20, "Blue", 0)],
            )
        self.original_keys = query_key_table(self.path, Key())

    def test_updates_only_supplied_fields_and_returns_complete_key(self):
        keys = update_key_table(self.path, Key(key_id=7, name="Spare"))

        expected = Key(
            key_id=7, current_holder_id=10, owner_member_id=10,
            is_active=True, name="Spare", is_in_mailbox=True,
        )
        self.assertEqual([expected], keys)
        self.assertEqual(
            [expected, self.original_keys[1]], query_key_table(self.path, Key()),
        )

    def test_updates_all_mutable_fields_including_false_flags(self):
        update = Key(
            key_id=7, current_holder_id=20, owner_member_id=20,
            is_active=False, name="Owner's spare", is_in_mailbox=False,
        )

        self.assertEqual([update], update_key_table(self.path, update))
        self.assertEqual(
            [update, self.original_keys[1]], query_key_table(self.path, Key()),
        )

    def test_id_without_updates_returns_existing_key_unchanged(self):
        self.assertEqual(
            [self.original_keys[0]], update_key_table(self.path, Key(key_id=7)),
        )
        self.assertEqual(self.original_keys, query_key_table(self.path, Key()))

    def test_missing_key_returns_empty_list_without_creating_a_key(self):
        self.assertEqual(
            [], update_key_table(self.path, Key(key_id=999, name="Missing")),
        )
        self.assertEqual([], update_key_table(self.path, Key(key_id=999)))
        self.assertEqual(self.original_keys, query_key_table(self.path, Key()))

    def test_missing_id_is_rejected_without_updating_any_key(self):
        for update in (Key(), Key(name="Spare")):
            with self.subTest(update=update):
                with self.assertRaisesRegex(ValueError, "key_id is required"):
                    update_key_table(self.path, update)
        self.assertEqual(self.original_keys, query_key_table(self.path, Key()))

    def test_key_name_is_stored_as_a_literal_value(self):
        name = "Spare', is_active = 0 WHERE id = 8 --"

        keys = update_key_table(self.path, Key(key_id=7, name=name))

        self.assertEqual(name, keys[0].name)
        self.assertIs(keys[0].is_active, True)
        self.assertEqual(
            [self.original_keys[1]], query_key_table(self.path, Key(key_id=8)),
        )

    def test_invalid_member_reference_rolls_back_all_supplied_fields(self):
        for field in ("current_holder_id", "owner_member_id"):
            with self.subTest(field=field):
                update = Key(key_id=7, name="Changed", **{field: 999})
                with self.assertRaises(sqlite3.IntegrityError):
                    update_key_table(self.path, update)
                self.assertEqual(self.original_keys, query_key_table(self.path, Key()))

    def test_invalid_mailbox_flag_rolls_back_all_supplied_fields(self):
        with self.assertRaises(sqlite3.IntegrityError):
            update_key_table(self.path, Key(key_id=7, name="Changed", is_in_mailbox=2))

        self.assertEqual(self.original_keys, query_key_table(self.path, Key()))


if __name__ == "__main__":
    unittest.main()
