import asyncio
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from src import admin_command_handlers, bot, command_handlers_utility, handover_flow, messages
from src.admin_commands import UPDATE_KEY_ADMIN_COMMAND, load_command_documentation
from src.command_handlers_utility import (
    UpdateKeyUsageError,
    format_key_changes,
    parse_update_key_command_arguments,
)
from src.config import DATABASE_PATH
from src.database import (
    database_connection,
    get_gym_member_by_telegram_user_id,
    get_key_history,
    initialize_database,
    query_key_table,
)
from src.key_service import KeyUpdateMemberNotFoundError, KeyUpdateResult
from src.models import GymMember, Key


class UpdateKeyArgumentTests(unittest.TestCase):
    def setUp(self):
        self.lookup = self.enterContext(patch.object(
            command_handlers_utility, "get_gym_member_by_telegram_user_id",
            side_effect=lambda path, telegram_id: GymMember(
                id={100: 10, 200: 20}.get(telegram_id, telegram_id),
                telegram_user_id=telegram_id,
            ),
        ))
        self.enterContext(patch.object(
            command_handlers_utility, "query_gym_member_records",
            side_effect=lambda path, member: [GymMember(id=member.id, telegram_user_id=member.id * 10)],
        ))

    def test_parses_all_fields_with_short_or_long_options(self):
        for options in (
            ["-m", "tRuE", "-n", "Spare", "-a", "FALSE", "-o", "100", "-c", "200"],
            ["--owner", "100", "--current-holder", "200", "--activate", "false",
             "--name", "Spare", "--mailbox", "TRUE"],
        ):
            with self.subTest(options=options):
                self.assertEqual(
                    Key(key_id=7, current_holder_id=20, owner_member_id=10,
                        is_active=False, name="Spare", is_in_mailbox=True),
                    parse_update_key_command_arguments(["7", *options], "selected.sqlite3"),
                )

    def test_omitted_fields_remain_unset_and_false_is_preserved(self):
        self.assertEqual(
            Key(key_id=7, is_active=False, is_in_mailbox=False),
            parse_update_key_command_arguments(["7", "-a", "False", "--mailbox", "false"], "selected.sqlite3"),
        )

    def test_resolves_telegram_ids_using_the_supplied_database(self):
        result = parse_update_key_command_arguments(["7", "-o", "100"], "selected.sqlite3")
        self.assertEqual(Key(key_id=7, owner_member_id=10), result)
        self.lookup.assert_called_once_with("selected.sqlite3", 100)

    def test_missing_member_error_preserves_the_telegram_id(self):
        self.lookup.return_value = None
        self.lookup.side_effect = None
        with self.assertRaises(KeyUpdateMemberNotFoundError) as error:
            parse_update_key_command_arguments(["7", "-c", "999"], "selected.sqlite3")
        self.assertEqual(999, error.exception.telegram_user_id)

    def test_rejects_missing_unknown_and_duplicate_options(self):
        for args in (
            [], ["7"], ["7", "-n"], ["7", "-n", "Spare", "-m"],
            ["7", "--unknown", "value"], ["7", "--name", "--mailbox"],
            ["7", "-n", "Spare", "--name", "Other"],
            ["7", "-a", "True", "--activate", "False"],
            ["7", "-m", "True", "--mailbox", "False"],
            ["7", "-c", "10", "--current-holder", "20"],
            ["7", "-o", "10", "--owner", "200"],
        ):
            with self.subTest(args=args), self.assertRaises(UpdateKeyUsageError):
                parse_update_key_command_arguments(args, "selected.sqlite3")

    def test_rejects_invalid_ids_flags_and_blank_names(self):
        for args in (
            ["bad", "-n", "Spare"], ["0", "-n", "Spare"], ["-7", "-n", "Spare"],
            ["7", "-c", "0"], ["7", "-c", "-20"], ["7", "-o", "bad"],
            ["7", "-o", "0"], ["7", "-o", str(2**63)],
            ["7", "-o", "-10"], ["7", "-a", "yes"], ["7", "-a", "1"],
            ["7", "-m", "no"], ["7", "-m", "0"],
            ["7", "-n", ""], ["7", "-n", "   "],
            [str(2**63), "-n", "Spare"], ["7", "-c", str(2**63)],
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                parse_update_key_command_arguments(args, "selected.sqlite3")

    def test_accepts_largest_sqlite_identifier(self):
        identifier = 2**63 - 1
        self.assertEqual(
            Key(key_id=identifier, current_holder_id=identifier, owner_member_id=identifier),
            parse_update_key_command_arguments(
                [str(identifier), "-c", str(identifier), "-o", str(identifier)],
                "selected.sqlite3",
            ),
        )

    def test_formats_actual_changes_including_false_flags(self):
        before = Key(7, 10, 10, True, "Red", True)
        after = replace(before, current_holder_id=20, is_active=False, is_in_mailbox=False)
        self.assertEqual(
            "Current holder Telegram ID: 100 -> 200\nActive: True -> False\nIn mailbox: True -> False",
            format_key_changes(before, after, "selected.sqlite3"),
        )
        self.assertEqual("", format_key_changes(before, before, "selected.sqlite3"))


class UpdateKeyCommandTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.message = SimpleNamespace(reply_text=AsyncMock())
        self.update = SimpleNamespace(effective_message=self.message, effective_user=SimpleNamespace(id=100))
        self.lookup = self.enterContext(patch.object(
            admin_command_handlers, "get_gym_member_by_telegram_user_id",
            return_value=GymMember(telegram_user_id=100, is_admin=True),
        ))
        self.before = Key(7, 20, 10, True, "Red", False)
        self.after = replace(self.before, name="Spare")
        self.update_key = self.enterContext(patch.object(
            admin_command_handlers, "update_key", return_value=KeyUpdateResult(self.before, self.after),
        ))
        self.cancel = self.enterContext(patch.object(admin_command_handlers, "cancel_pending_handover"))

    async def invoke(self, args):
        await admin_command_handlers.update_key_command_handler(self.update, SimpleNamespace(args=args))

    async def test_rejects_unregistered_and_non_admin_requesters(self):
        for requester, reply in (
            (None, messages.AUTH_USER_UNREGISTERED_TEXT),
            (GymMember(is_admin=False), messages.ADMIN_COMMAND_FORBIDDEN_TEXT),
        ):
            with self.subTest(requester=requester):
                self.lookup.return_value = requester
                self.message.reply_text.reset_mock()
                await self.invoke(["7", "-n", "Spare"])
                self.message.reply_text.assert_awaited_once_with(reply)
                self.update_key.assert_not_called()
                self.cancel.assert_not_called()

    async def test_help_ignores_other_arguments_without_updating(self):
        for option in ("-h", "--help"):
            with self.subTest(option=option):
                self.message.reply_text.reset_mock()
                await self.invoke(["bad", "--unknown", "value", option])
                self.message.reply_text.assert_awaited_once_with(
                    load_command_documentation(UPDATE_KEY_ADMIN_COMMAND), parse_mode="MarkdownV2",
                )
        self.update_key.assert_not_called()
        self.cancel.assert_not_called()

    async def test_invalid_arguments_do_not_write(self):
        for args, reply in (
            ([], messages.ADMIN_UPDATE_KEY_USAGE_TEXT),
            (["7", "-n"], messages.ADMIN_UPDATE_KEY_USAGE_TEXT),
            (["7", "--unknown", "value"], messages.ADMIN_UPDATE_KEY_USAGE_TEXT),
            (["7", "-a", "yes"], messages.ADMIN_BAD_VALUE_TEXT),
            (["7", "-c", "0"], messages.ADMIN_BAD_VALUE_TEXT),
            ([str(2**63), "-n", "Spare"], messages.ADMIN_BAD_VALUE_TEXT),
            (["7", "-c", str(2**63)], messages.ADMIN_BAD_VALUE_TEXT),
            (["7", "-o", str(2**63)], messages.ADMIN_BAD_VALUE_TEXT),
            (["bad", "-n", "Spare"], messages.ADMIN_BAD_VALUE_TEXT),
        ):
            with self.subTest(args=args):
                self.message.reply_text.reset_mock()
                await self.invoke(args)
                self.message.reply_text.assert_awaited_once_with(reply)
        self.update_key.assert_not_called()
        self.cancel.assert_not_called()

    async def test_updates_supplied_fields_and_reports_changes(self):
        await self.invoke(["7", "--name", "Spare"])
        self.update_key.assert_called_once_with(DATABASE_PATH, Key(key_id=7, name="Spare"))
        self.message.reply_text.assert_awaited_once_with("Updated key 7 (Spare):\nName: Red -> Spare")
        self.cancel.assert_not_called()

    async def test_reports_no_actual_changes_without_cancelling_handover(self):
        self.update_key.return_value = KeyUpdateResult(self.before, self.before)
        await self.invoke(["7", "-n", "Red"])
        self.message.reply_text.assert_awaited_once_with("No key data changed for key 7 (Red).")
        self.cancel.assert_not_called()

    async def test_reports_missing_key_without_cancelling_handover(self):
        self.update_key.return_value = None
        await self.invoke(["99", "-n", "Spare"])
        self.message.reply_text.assert_awaited_once_with(messages.KEY_NOT_FOUND_TEXT.format(key_id=99))
        self.cancel.assert_not_called()

    async def test_missing_member_is_reported_before_writing(self):
        with patch.object(
            command_handlers_utility, "get_gym_member_by_telegram_user_id", return_value=None,
        ) as lookup:
            await self.invoke(["7", "-c", "999"])
        lookup.assert_called_once_with(DATABASE_PATH, 999)
        self.message.reply_text.assert_awaited_once_with(
            messages.ADMIN_UPDATE_KEY_MEMBER_NOT_FOUND_TEXT.format(telegram_user_id=999),
        )
        self.update_key.assert_not_called()
        self.cancel.assert_not_called()

    async def test_unexpected_storage_errors_propagate_without_success_or_cancellation(self):
        self.update_key.side_effect = sqlite3.OperationalError("database unavailable")
        with self.assertRaisesRegex(sqlite3.OperationalError, "database unavailable"):
            await self.invoke(["7", "-n", "Spare"])
        self.message.reply_text.assert_not_called()
        self.cancel.assert_not_called()


class UpdateKeyIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.path = Path(directory) / "keys.sqlite3"
        initialize_database(self.path)
        with database_connection(self.path) as connection:
            connection.executemany(
                """INSERT INTO gym_members (id, telegram_user_id, name, surname, room_number, is_admin)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [(10, 100, "Ada", "Owner", 101, 1), (20, 200, "Ben", "Holder", 202, 0),
                 (30, 300, "Cara", "Receiver", 303, 0)],
            )
            connection.executemany(
                """INSERT INTO keys (id, current_holder_id, owner_member_id, name)
                   VALUES (?, ?, ?, ?)""",
                [(7, 20, 10, "Red"), (8, 10, 10, "Blue")],
            )
        self.original = query_key_table(self.path, Key())
        self.message = SimpleNamespace(reply_text=AsyncMock())
        self.update = SimpleNamespace(effective_message=self.message, effective_user=SimpleNamespace(id=100))
        self.enterContext(patch.object(admin_command_handlers, "DATABASE_PATH", self.path))
        self.enterContext(patch.object(handover_flow, "DATABASE_PATH", self.path))
        self.addCleanup(handover_flow.cancel_pending_handover, 7)

    async def invoke(self, options, key_id=7):
        await admin_command_handlers.update_key_command_handler(
            self.update, SimpleNamespace(args=[str(key_id), *options]),
        )

    def current_key(self):
        return query_key_table(self.path, Key(key_id=7))[0]

    def assert_history(self, expected):
        records = get_key_history(self.path, 7)
        self.assertEqual(expected, [(record.member.id, record.put_into_mailbox) for record in records])

    def start_handover(self):
        holder = get_gym_member_by_telegram_user_id(self.path, 200)
        handover_flow.start_pending_handover(7, holder, SimpleNamespace(), AsyncMock())
        return handover_flow.get_pending_handover(7)

    async def test_updates_all_fields_together_and_records_one_history_entry(self):
        await self.invoke(["--name", "Spare", "-c", "300", "--owner", "200", "-a", "False", "-m", "True"])
        self.assertEqual(Key(7, 30, 20, False, "Spare", True), self.current_key())
        self.assertEqual([self.original[1]], query_key_table(self.path, Key(key_id=8)))
        self.assert_history([(30, True)])
        self.message.reply_text.assert_awaited_once_with(
            "Updated key 7 (Spare):\nCurrent holder Telegram ID: 200 -> 300\nOwner Telegram ID: 100 -> 200\n"
            "Active: True -> False\nName: Red -> Spare\nIn mailbox: False -> True",
        )

    async def test_missing_references_do_not_partially_update_key_or_history(self):
        pending = self.start_handover()
        for option in ("-c", "--owner"):
            with self.subTest(option=option):
                self.message.reply_text.reset_mock()
                await self.invoke(["-n", "Changed", "-m", "True", option, "999"])
                self.assertEqual(self.original, query_key_table(self.path, Key()))
                self.assert_history([])
                self.assertIs(pending, handover_flow.get_pending_handover(7))
                self.message.reply_text.assert_awaited_once_with(
                    messages.ADMIN_UPDATE_KEY_MEMBER_NOT_FOUND_TEXT.format(telegram_user_id=999),
                )

    async def test_missing_key_does_not_create_a_key(self):
        await self.invoke(["-n", "Spare"], key_id=999)
        self.assertEqual(self.original, query_key_table(self.path, Key()))
        self.assert_history([])
        self.message.reply_text.assert_awaited_once_with(messages.KEY_NOT_FOUND_TEXT.format(key_id=999))

    async def test_existing_internal_ids_are_not_accepted_as_telegram_ids(self):
        pending = self.start_handover()
        for option in ("-c", "--owner"):
            with self.subTest(option=option):
                self.message.reply_text.reset_mock()
                await self.invoke(["-n", "Changed", option, "20"])
                self.message.reply_text.assert_awaited_once_with(
                    messages.ADMIN_UPDATE_KEY_MEMBER_NOT_FOUND_TEXT.format(telegram_user_id=20),
                )
                self.assertEqual(self.original, query_key_table(self.path, Key()))
                self.assert_history([])
                self.assertIs(pending, handover_flow.get_pending_handover(7))

    async def test_telegram_id_wins_when_it_matches_another_members_internal_id(self):
        with database_connection(self.path) as connection:
            connection.execute(
                """INSERT INTO gym_members (id, telegram_user_id, name, surname, room_number)
                   VALUES (300, 400, 'Dana', 'Other', 404)""",
            )
        await self.invoke(["-c", "300", "--owner", "300"])
        self.assertEqual(
            replace(self.original[0], current_holder_id=30, owner_member_id=30),
            self.current_key(),
        )
        self.assert_history([(30, False)])
        self.message.reply_text.assert_awaited_once_with(
            "Updated key 7 (Red):\nCurrent holder Telegram ID: 200 -> 300\n"
            "Owner Telegram ID: 100 -> 300",
        )

    async def test_mailbox_change_records_location_for_the_same_holder(self):
        await self.invoke(["-m", "True"])
        self.assertEqual(replace(self.original[0], is_in_mailbox=True), self.current_key())
        self.assert_history([(20, True)])
        await self.invoke(["--mailbox", "False"])
        self.assertEqual(self.original[0], self.current_key())
        self.assert_history([(20, False), (20, True)])

    async def test_holder_change_preserves_unspecified_mailbox_location(self):
        await self.invoke(["-m", "True"])
        await self.invoke(["-c", "300"])
        self.assertEqual(replace(self.original[0], current_holder_id=30, is_in_mailbox=True), self.current_key())
        self.assert_history([(30, True), (20, True)])

    async def test_metadata_and_unchanged_values_preserve_history_and_handover(self):
        pending = self.start_handover()
        for options in (
            ["-n", "Spare", "-o", "300"],
            ["-c", "200", "-m", "False", "-a", "True"],
        ):
            await self.invoke(options)
            self.assertIs(pending, handover_flow.get_pending_handover(7))
            self.assert_history([])
        self.assertEqual(replace(self.original[0], name="Spare", owner_member_id=30), self.current_key())
        self.assertEqual("No key data changed for key 7 (Spare).", self.message.reply_text.await_args.args[0])

    async def test_state_changes_cancel_handover_and_block_old_confirmation(self):
        for options in (["-c", "300"], ["-m", "True"], ["-a", "False"]):
            with self.subTest(options=options):
                with database_connection(self.path) as connection:
                    connection.execute(
                        "UPDATE keys SET current_holder_id = 20, is_in_mailbox = 0, is_active = 1 WHERE id = 7",
                    )
                pending = self.start_handover()
                await self.invoke(options)
                state = self.current_key()
                history = [(record.event_id, record.member.id) for record in get_key_history(self.path, 7)]
                self.assertIsNone(handover_flow.get_pending_handover(7))
                await asyncio.sleep(0)
                self.assertTrue(pending.timeout_task.cancelled())
                query = SimpleNamespace(answer=AsyncMock(), from_user=SimpleNamespace(id=300))
                reply = AsyncMock()
                message = SimpleNamespace()
                await handover_flow.handle_pending_handover_confirmation(7, query, message, reply)
                reply.assert_awaited_once_with(
                    message, messages.HANDOVER_RECEIVER_MISSING_TEXT.format(key_id=state.label), 300,
                )
                self.assertEqual(state, self.current_key())
                self.assertEqual(history, [(record.event_id, record.member.id) for record in get_key_history(self.path, 7)])

    async def test_history_failure_rolls_back_all_fields_and_keeps_handover(self):
        pending = self.start_handover()
        with database_connection(self.path) as connection:
            connection.execute(
                """CREATE TRIGGER reject_holder_history BEFORE INSERT ON key_holder_history
                   BEGIN SELECT RAISE(ABORT, 'history write failed'); END""",
            )
        with self.assertRaisesRegex(sqlite3.IntegrityError, "history write failed"):
            await self.invoke(["-c", "300", "-m", "True", "-n", "Changed", "-a", "False"])
        self.assertEqual(self.original, query_key_table(self.path, Key()))
        self.assert_history([])
        self.assertIs(pending, handover_flow.get_pending_handover(7))
        self.message.reply_text.assert_not_called()

    async def test_inactive_key_can_be_reactivated(self):
        await self.invoke(["--activate", "False"])
        await self.invoke(["--activate", "True"])
        self.assertEqual(self.original[0], self.current_key())
        self.assert_history([])

class UpdateKeyRegistrationTests(unittest.TestCase):
    def test_bot_registers_update_key_handler(self):
        application = MagicMock()
        builder = MagicMock()
        for method in ("token", "concurrent_updates", "read_timeout", "write_timeout"):
            getattr(builder, method).return_value = builder
        builder.build.return_value = application
        with (
            patch.object(bot, "initialize_database"),
            patch.object(bot.Application, "builder", return_value=builder),
            patch("builtins.print"),
        ):
            bot.main()
        handlers = [call.args[0] for call in application.add_handler.call_args_list]
        handler = next(handler for handler in handlers if UPDATE_KEY_ADMIN_COMMAND in getattr(handler, "commands", ()))
        self.assertIs(handler.callback, admin_command_handlers.update_key_command_handler)


if __name__ == "__main__":
    unittest.main()
