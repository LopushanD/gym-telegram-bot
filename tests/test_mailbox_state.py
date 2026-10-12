import sqlite3
import tempfile
import unittest
from pathlib import Path

from src.database import (
    change_key_holder,
    database_connection,
    get_active_keys,
    get_all_current_keyholders_info,
    get_current_keyholder_info,
    get_key_history,
    get_key_id_by_telegram_user_id,
    get_key_return_instruction_info,
    get_key_status,
    initialize_database,
    populate_test_mailboxes_and_keys,
    query_key_table,
    set_key_active,
    set_key_owner,
)
from src.key_service import (
    GiveKeyStatus,
    HandoverStatus,
    ReturnToMailboxStatus,
    TakeFromMailboxStatus,
    can_start_key_handover,
    give_key_to_member,
    return_key_to_mailbox,
    take_key_from_mailbox,
    user_currently_holds_any_key,
    user_currently_holds_key,
)
from src.messages import current_key_holder_text, key_status_text
from src.models import Key


class MailboxStateTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.path = Path(directory) / "keys.sqlite3"
        initialize_database(self.path)
        with database_connection(self.path) as connection:
            connection.executemany(
                """INSERT INTO gym_members (id, telegram_user_id, name, surname, room_number)
                   VALUES (?, ?, ?, ?, ?)""",
                [(1, 100, "Ada", "Owner", 101), (2, 200, "Alex", "Holder", 202)],
            )
            connection.executemany(
                """INSERT INTO keys
                   (id, name, current_holder_id, owner_member_id, is_in_mailbox, is_active)
                   VALUES (?, ?, ?, 1, ?, ?)""",
                [(1, "Red", 2, 0, 1), (2, "Blue", 1, 0, 1),
                 (3, "Green", 1, 1, 1), (4, "Old", 1, 1, 0)],
            )

    def key_state(self, key_id):
        with database_connection(self.path) as connection:
            return connection.execute(
                "SELECT current_holder_id, owner_member_id, is_in_mailbox FROM keys WHERE id = ?",
                (key_id,),
            ).fetchone()

    def history_holders(self, key_id):
        with database_connection(self.path) as connection:
            return connection.execute(
                "SELECT holder_id FROM key_holder_history WHERE key_id = ? ORDER BY event_id",
                (key_id,),
            ).fetchall()

    def test_return_and_pickup_update_holder_and_location_and_record_history(self):
        self.assertEqual(
            ReturnToMailboxStatus.RETURNED, return_key_to_mailbox(self.path, 200, 1).status
        )
        self.assertEqual((1, 1, 1), self.key_state(1))
        self.assertFalse(user_currently_holds_key(self.path, 100, 1))
        self.assertEqual(
            TakeFromMailboxStatus.TAKEN, take_key_from_mailbox(self.path, 200, 1).status
        )
        self.assertEqual((2, 1, 0), self.key_state(1))
        self.assertTrue(user_currently_holds_key(self.path, 200, 1))
        self.assertEqual([(1,), (2,)], self.history_holders(1))

    def test_owner_can_take_their_key_from_mailbox_and_return_it(self):
        self.assertEqual(
            TakeFromMailboxStatus.TAKEN, take_key_from_mailbox(self.path, 100, 3).status
        )
        self.assertEqual((1, 1, 0), self.key_state(3))
        self.assertTrue(user_currently_holds_key(self.path, 100, 3))
        self.assertEqual(
            ReturnToMailboxStatus.RETURNED, return_key_to_mailbox(self.path, 100, 3).status
        )
        self.assertEqual((1, 1, 1), self.key_state(3))
        self.assertEqual([(1,), (1,)], self.history_holders(3))

    def test_mailbox_pickup_rejects_key_in_owners_hands(self):
        for telegram_user_id in (100, 200):
            with self.subTest(telegram_user_id=telegram_user_id):
                self.assertEqual(
                    TakeFromMailboxStatus.KEY_NOT_IN_MAILBOX,
                    take_key_from_mailbox(self.path, telegram_user_id, 2).status,
                )
        self.assertEqual((1, 1, 0), self.key_state(2))
        self.assertEqual([], self.history_holders(2))

    def test_mailbox_pickup_cannot_be_confirmed_twice(self):
        self.assertEqual(TakeFromMailboxStatus.TAKEN, take_key_from_mailbox(self.path, 200, 3).status)
        self.assertEqual(
            TakeFromMailboxStatus.KEY_NOT_IN_MAILBOX, take_key_from_mailbox(self.path, 100, 3).status
        )
        self.assertEqual((2, 1, 0), self.key_state(3))
        self.assertEqual([(2,)], self.history_holders(3))

    def test_return_rejects_non_holder_and_key_already_in_mailbox(self):
        for telegram_user_id, key_id in ((100, 1), (100, 3), (200, 3), (None, 1)):
            with self.subTest(telegram_user_id=telegram_user_id, key_id=key_id):
                self.assertEqual(
                    ReturnToMailboxStatus.NOT_CURRENT_HOLDER,
                    return_key_to_mailbox(self.path, telegram_user_id, key_id).status,
                )
        self.assertEqual((2, 1, 0), self.key_state(1))
        self.assertEqual((1, 1, 1), self.key_state(3))
        self.assertEqual([], self.history_holders(1))
        self.assertEqual([], self.history_holders(3))

    def test_mailbox_owner_has_no_holder_actions_until_they_take_a_key(self):
        # Remove the owner's key in hand, leaving only mailbox keys.
        change_key_holder(self.path, 2, 2)
        self.assertFalse(user_currently_holds_any_key(self.path, 100))
        self.assertIsNone(get_key_return_instruction_info(self.path, 100))
        self.assertIsNone(get_key_id_by_telegram_user_id(self.path, 100))
        self.assertEqual(
            HandoverStatus.NOT_CURRENT_HOLDER, can_start_key_handover(self.path, 100, 3).status
        )
        take_key_from_mailbox(self.path, 100, 3)
        self.assertTrue(user_currently_holds_any_key(self.path, 100))
        self.assertEqual((3, "Green", 101), get_key_return_instruction_info(self.path, 100))
        self.assertEqual(3, get_key_id_by_telegram_user_id(self.path, 100))
        self.assertEqual(HandoverStatus.READY, can_start_key_handover(self.path, 100, 3).status)

    def test_normal_transfer_clears_mailbox_flag(self):
        change_key_holder(self.path, 3, 2)
        self.assertEqual((2, 1, 0), self.key_state(3))
        self.assertEqual([(2,)], self.history_holders(3))

    def test_admin_give_key_clears_mailbox_flag_even_when_given_to_owner(self):
        self.assertEqual(GiveKeyStatus.GIVEN, give_key_to_member(self.path, 3, 100).status)
        self.assertEqual((1, 1, 0), self.key_state(3))
        self.assertEqual([(1,)], self.history_holders(3))

    def test_mailbox_delivery_can_target_a_member_other_than_the_owner(self):
        change_key_holder(self.path, 3, 2, is_in_mailbox=True)
        self.assertEqual((2, 1, 1), self.key_state(3))
        self.assertEqual([(2,)], self.history_holders(3))
        text = current_key_holder_text(get_current_keyholder_info(self.path, 3))
        for expected in ("Alex Holder", "mailbox", "room 202"):
            self.assertIn(expected, text)

    def test_admin_delivery_sets_location_from_receiving_side_only(self):
        for previous_flag in (False, True):
            for is_in_mailbox in (False, True):
                for member_id, telegram_user_id in ((1, 100), (2, 200)):
                    with self.subTest(previous_flag=previous_flag, is_in_mailbox=is_in_mailbox,
                                      member_id=member_id):
                        with database_connection(self.path) as connection:
                            connection.execute(
                                "UPDATE keys SET current_holder_id = 1, is_in_mailbox = ? WHERE id = 3",
                                (previous_flag,),
                            )
                        result = give_key_to_member(
                            self.path, 3, telegram_user_id, is_in_mailbox=is_in_mailbox
                        )
                        self.assertEqual(GiveKeyStatus.GIVEN, result.status)
                        self.assertEqual((member_id, 1, int(is_in_mailbox)), self.key_state(3))
        self.assertEqual([(1,), (2,)] * 4, self.history_holders(3))

    def test_pickup_from_non_owners_mailbox_records_recipient_in_hands(self):
        give_key_to_member(self.path, 3, 200, is_in_mailbox=True)
        self.assertEqual(TakeFromMailboxStatus.TAKEN, take_key_from_mailbox(self.path, 100, 3).status)
        self.assertEqual((1, 1, 0), self.key_state(3))
        self.assertEqual([(2,), (1,)], self.history_holders(3))

    def test_history_failure_rolls_back_holder_and_mailbox_flag(self):
        with database_connection(self.path) as connection:
            connection.execute("""
                CREATE TRIGGER reject_history BEFORE INSERT ON key_holder_history
                BEGIN SELECT RAISE(ABORT, 'history unavailable'); END
            """)
        with self.assertRaisesRegex(sqlite3.IntegrityError, "history unavailable"):
            return_key_to_mailbox(self.path, 200, 1)
        self.assertEqual((2, 1, 0), self.key_state(1))
        self.assertEqual([], self.history_holders(1))

    def test_failed_pickup_or_admin_delivery_rolls_back_state_and_history(self):
        with database_connection(self.path) as connection:
            connection.execute("""
                CREATE TRIGGER reject_history BEFORE INSERT ON key_holder_history
                BEGIN SELECT RAISE(ABORT, 'history unavailable'); END
            """)
        operations = (
            (3, lambda: take_key_from_mailbox(self.path, 200, 3)),
            (3, lambda: give_key_to_member(self.path, 3, 200)),
            (1, lambda: give_key_to_member(self.path, 1, 100, is_in_mailbox=True)),
        )
        for key_id, operation in operations:
            with self.subTest(key_id=key_id, operation=operation):
                state_before = self.key_state(key_id)
                with self.assertRaisesRegex(sqlite3.IntegrityError, "history unavailable"):
                    operation()
                self.assertEqual(state_before, self.key_state(key_id))
                self.assertEqual([], self.history_holders(key_id))

    def test_invalid_destination_flag_cannot_change_holder_or_history(self):
        for flag in (None, -1, 2):
            with self.subTest(flag=flag):
                with self.assertRaises(sqlite3.IntegrityError):
                    change_key_holder(self.path, 3, 2, is_in_mailbox=flag)
                self.assertEqual((1, 1, 1), self.key_state(3))
                self.assertEqual([], self.history_holders(3))

    def test_return_instruction_and_handover_selection_skip_mailbox_keys(self):
        change_key_holder(self.path, 1, 2, is_in_mailbox=True)
        change_key_holder(self.path, 2, 2)
        self.assertEqual((2, "Blue", 101), get_key_return_instruction_info(self.path, 200))
        self.assertEqual(2, get_key_id_by_telegram_user_id(self.path, 200))

    def test_activation_changes_do_not_change_location_or_add_history(self):
        for key_id in (1, 3):
            state_before = self.key_state(key_id)
            for active in (False, True):
                with self.subTest(key_id=key_id, active=active):
                    self.assertTrue(set_key_active(self.path, key_id, active))
                    self.assertEqual(state_before, self.key_state(key_id))
                    self.assertIs(get_key_status(self.path, key_id)[0].is_active, active)
                    self.assertEqual([], self.history_holders(key_id))

    def test_owner_change_preserves_location_and_changes_return_destination(self):
        self.assertTrue(set_key_owner(self.path, 1, 2))
        self.assertEqual((2, 2, 0), self.key_state(1))
        self.assertEqual((1, "Red", 202), get_key_return_instruction_info(self.path, 200))
        self.assertEqual([], self.history_holders(1))
        self.assertEqual(ReturnToMailboxStatus.RETURNED, return_key_to_mailbox(self.path, 200, 1).status)
        self.assertEqual((2, 2, 1), self.key_state(1))
        self.assertEqual([(2,)], self.history_holders(1))

    def test_queries_expose_mailbox_state_and_support_both_flag_filters(self):
        for key_id in (1, 2, 3, 4):
            with self.subTest(key_id=key_id):
                key, member, _ = get_key_status(self.path, key_id)
                holder = get_current_keyholder_info(self.path, key_id)
                self.assertEqual(key, holder.key)
                self.assertEqual(member, holder.member)
                self.assertIs(holder.key.is_active, key.is_active)
        self.assertIs(get_key_status(self.path, 3)[0].is_in_mailbox, True)
        self.assertIs(get_current_keyholder_info(self.path, 3).key.is_in_mailbox, True)
        holders = get_all_current_keyholders_info(self.path)
        self.assertEqual(get_active_keys(self.path), [holder.key for holder in holders])
        self.assertEqual([False, False, True], [holder.key.is_in_mailbox for holder in holders])
        self.assertEqual([False, False, True], [key.is_in_mailbox for key in get_active_keys(self.path)])
        for flag, expected_ids in ((False, [1, 2]), (True, [3, 4])):
            with self.subTest(is_in_mailbox=flag):
                keys = query_key_table(self.path, Key(is_in_mailbox=flag))
                self.assertEqual(expected_ids, sorted(key.key_id for key in keys))
        return_key_to_mailbox(self.path, 200, 1)
        self.assertIs(get_key_history(self.path, 1)[0].key.is_in_mailbox, True)

    def test_holder_info_and_admin_status_show_key_location(self):
        text = current_key_holder_text(get_current_keyholder_info(self.path, 3))
        for expected in ("Ada Owner", "mailbox", "room 101"):
            self.assertIn(expected, text)
        for key_id, location in ((2, "member's hands"), (3, "mailbox")):
            with self.subTest(key_id=key_id):
                text = key_status_text(*get_key_status(self.path, key_id))
                self.assertIn(f"Location: {location}", text)

    def test_new_keys_default_to_hands_and_reject_invalid_mailbox_flags(self):
        with database_connection(self.path) as connection:
            key_id = connection.execute(
                "INSERT INTO keys (current_holder_id, owner_member_id) VALUES (1, 1)"
            ).lastrowid
        self.assertEqual((1, 1, 0), self.key_state(key_id))
        for value in (None, -1, 2):
            with self.subTest(value=value):
                with self.assertRaises(sqlite3.IntegrityError), database_connection(self.path) as connection:
                    connection.execute("UPDATE keys SET is_in_mailbox = ? WHERE id = ?", (value, key_id))
        self.assertEqual((1, 1, 0), self.key_state(key_id))

    def test_reinitialization_preserves_explicit_location_even_when_owner_holds_key(self):
        initialize_database(self.path)
        initialize_database(self.path)
        self.assertEqual((1, 1, 0), self.key_state(2))
        self.assertEqual((1, 1, 1), self.key_state(3))

    def test_seeded_mailbox_keys_start_in_mailboxes(self):
        _, key_ids = populate_test_mailboxes_and_keys(self.path)
        for key_id in key_ids:
            holder, owner, flag = self.key_state(key_id)
            self.assertEqual(owner, holder)
            self.assertEqual(1, flag)


class MailboxMigrationTests(unittest.TestCase):
    def test_legacy_migration_defaults_location_to_hands_and_preserves_keys_and_history(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        path = Path(directory) / "legacy.sqlite3"
        with database_connection(path) as connection:
            connection.executescript("""
                CREATE TABLE keys (
                    id INTEGER PRIMARY KEY, name TEXT, current_holder_id INTEGER,
                    owner_member_id INTEGER, is_active INTEGER
                );
                INSERT INTO keys VALUES (1, 'Red', 10, 10, 1), (2, 'Blue', 20, 10, 1);
                CREATE TABLE key_holder_history (
                    event_id INTEGER PRIMARY KEY, key_id INTEGER,
                    holder_id INTEGER, taken_at TIMESTAMP
                );
                INSERT INTO key_holder_history VALUES (1, 2, 20, '2026-01-01 12:00:00');
            """)
        initialize_database(path)
        initialize_database(path)
        with database_connection(path) as connection:
            self.assertEqual(
                [(1, "Red", 10, 10, 1, 0), (2, "Blue", 20, 10, 1, 0)],
                connection.execute("SELECT * FROM keys ORDER BY id").fetchall(),
            )
            self.assertEqual(
                [(1, 2, 20, "2026-01-01 12:00:00")],
                connection.execute("SELECT * FROM key_holder_history").fetchall(),
            )
        with self.assertRaises(sqlite3.IntegrityError), database_connection(path) as connection:
            connection.execute("UPDATE keys SET is_in_mailbox = 2 WHERE id = 1")
        with database_connection(path) as connection:
            connection.execute("UPDATE keys SET is_in_mailbox = 1 WHERE id = 1")
        initialize_database(path)
        with database_connection(path) as connection:
            self.assertEqual([(1, 1), (2, 0)], connection.execute(
                "SELECT id, is_in_mailbox FROM keys ORDER BY id"
            ).fetchall())
