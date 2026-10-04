import sys
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, call, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src import messages
from src.admin_commands import (
    ACTIVATE_KEY_ADMIN_COMMAND,
    ADD_USER_ADMIN_COMMAND,
    CHANGE_KEY_OWNER_ADMIN_COMMAND,
    DEACTIVATE_KEY_ADMIN_COMMAND,
    GIVE_KEY_ADMIN_COMMAND,
    SHOW_KEY_HISTORY_ADMIN_COMMAND,
    SHOW_KEY_STATUS_ADMIN_COMMAND,
    SHOW_USERS_ADMIN_COMMAND,
    UPDATE_USER_ADMIN_COMMAND,
    load_command_documentation,
)
from src.admin_command_handlers import (
    UpdateUserUsageError,
    activate_key_command_handler,
    add_user_command_handler,
    change_key_owner_command_handler,
    deactivate_key_command_handler,
    format_gym_member_changes,
    give_key_command_handler,
    key_history_command_handler,
    key_status_command_handler,
    parse_update_user_command_arguments,
    update_user_command_handler,
    users_command_handler,
)
from src.command_handlers_utility import process_key_history_records
from src.config import DATABASE_PATH
from src.database import GymMemberAlreadyExistsError
from src.key_service import GiveKeyResult, GiveKeyStatus
from src.models import GymMember, KeyHistoryRecord, Key


def build_member(telegram_user_id: int, *, is_admin: bool = False) -> GymMember:
    return GymMember(
        id=10,
        telegram_user_id=telegram_user_id,
        name="Dima",
        surname="Ivanov",
        room_number=1234,
        telegram_name="@dima",
        is_admin=is_admin,
    )


class AdminCommandHelpTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.message = SimpleNamespace(reply_text=AsyncMock())
        self.update = SimpleNamespace(
            effective_message=self.message,
            effective_user=SimpleNamespace(id=100),
        )

    async def test_add_user_help_replies_with_command_documentation(self):
        with (
            patch(
                "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                return_value=build_member(100, is_admin=True),
            ),
            patch("src.admin_command_handlers.add_gym_member") as add_member,
        ):
            await add_user_command_handler(
                self.update,
                SimpleNamespace(args=["-h"]),
            )

        self.message.reply_text.assert_awaited_once_with(
            load_command_documentation(ADD_USER_ADMIN_COMMAND),
            parse_mode="MarkdownV2",
        )
        add_member.assert_not_called()

    async def test_update_user_help_replies_with_command_documentation(self):
        with (
            patch(
                "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                return_value=build_member(100, is_admin=True),
            ),
            patch("src.admin_command_handlers.update_gym_member") as update_member,
        ):
            await update_user_command_handler(
                self.update,
                SimpleNamespace(args=["--help"]),
            )

        self.message.reply_text.assert_awaited_once_with(
            load_command_documentation(UPDATE_USER_ADMIN_COMMAND),
            parse_mode="MarkdownV2",
        )
        update_member.assert_not_called()

    async def test_all_admin_command_help_options_use_command_documentation(self):
        cases = (
            (
                CHANGE_KEY_OWNER_ADMIN_COMMAND,
                change_key_owner_command_handler,
                "src.admin_command_handlers.set_key_owner",
            ),
            (
                GIVE_KEY_ADMIN_COMMAND,
                give_key_command_handler,
                "src.admin_command_handlers.give_key_to_member",
            ),
            (
                SHOW_USERS_ADMIN_COMMAND,
                users_command_handler,
                "src.admin_command_handlers.query_gym_member_records",
            ),
            (
                SHOW_KEY_HISTORY_ADMIN_COMMAND,
                key_history_command_handler,
                "src.admin_command_handlers.get_key_history",
            ),
            (
                SHOW_KEY_STATUS_ADMIN_COMMAND,
                key_status_command_handler,
                "src.admin_command_handlers.get_key_status",
            ),
            (
                ACTIVATE_KEY_ADMIN_COMMAND,
                activate_key_command_handler,
                "src.admin_command_handlers.set_key_active",
            ),
            (
                DEACTIVATE_KEY_ADMIN_COMMAND,
                deactivate_key_command_handler,
                "src.admin_command_handlers.set_key_active",
            ),
        )

        for command_name, handler, service_path in cases:
            with self.subTest(command_name=command_name):
                self.message.reply_text.reset_mock()
                with (
                    patch(
                        "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                        return_value=build_member(100, is_admin=True),
                    ),
                    patch(service_path) as service_call,
                ):
                    await handler(self.update, SimpleNamespace(args=["-h"]))

                self.message.reply_text.assert_awaited_once_with(
                    load_command_documentation(command_name),
                    parse_mode="MarkdownV2",
                )
                service_call.assert_not_called()


class GiveKeyCommandTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.message = SimpleNamespace(reply_text=AsyncMock())
        self.update = SimpleNamespace(
            effective_message=self.message,
            effective_user=SimpleNamespace(id=100),
        )

    async def test_rejects_non_admin(self):
        with (
            patch(
                "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                return_value=build_member(100),
            ),
            patch("src.admin_command_handlers.give_key_to_member") as give_key,
        ):
            await give_key_command_handler(
                self.update,
                SimpleNamespace(args=["1", "200"]),
            )

        self.message.reply_text.assert_awaited_once_with(
            messages.ADMIN_COMMAND_FORBIDDEN_TEXT,
        )
        give_key.assert_not_called()

    async def test_rejects_invalid_arguments(self):
        with (
            patch(
                "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                return_value=build_member(100, is_admin=True),
            ),
            patch("src.admin_command_handlers.give_key_to_member") as give_key,
        ):
            await give_key_command_handler(
                self.update,
                SimpleNamespace(args=["not-a-key", "200"]),
            )

        self.message.reply_text.assert_awaited_once_with(
            messages.ADMIN_BAD_VALUE_TEXT,
        )
        give_key.assert_not_called()

    async def test_reports_unregistered_target_member(self):
        with (
            patch(
                "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                return_value=build_member(100, is_admin=True),
            ),
            patch(
                "src.admin_command_handlers.give_key_to_member",
                return_value=GiveKeyResult(GiveKeyStatus.USER_NOT_REGISTERED),
            ),
        ):
            await give_key_command_handler(
                self.update,
                SimpleNamespace(args=["1", "200"]),
            )

        self.message.reply_text.assert_awaited_once_with(
            messages.ADMIN_GIVE_KEY_USER_NOT_REGISTERED_TEXT.format(
                telegram_user_id=200,
            ),
        )

    async def test_reports_missing_key(self):
        with (
            patch(
                "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                return_value=build_member(100, is_admin=True),
            ),
            patch(
                "src.admin_command_handlers.give_key_to_member",
                return_value=GiveKeyResult(GiveKeyStatus.KEY_NOT_FOUND),
            ),
        ):
            await give_key_command_handler(
                self.update,
                SimpleNamespace(args=["999", "200"]),
            )

        self.message.reply_text.assert_awaited_once_with(
            messages.KEY_NOT_FOUND_TEXT.format(key_id=999),
        )

    async def test_gives_key_and_reports_target_member(self):
        target_member = build_member(200)
        with (
            patch(
                "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                return_value=build_member(100, is_admin=True),
            ),
            patch(
                "src.admin_command_handlers.give_key_to_member",
                return_value=GiveKeyResult(GiveKeyStatus.GIVEN, target_member),
            ) as give_key,
            patch("src.admin_command_handlers.cancel_pending_handover") as cancel_handover,
        ):
            await give_key_command_handler(
                self.update,
                SimpleNamespace(args=["1", "200"]),
            )

        give_key.assert_called_once_with(DATABASE_PATH, 1, 200)
        cancel_handover.assert_called_once_with(1)
        self.message.reply_text.assert_awaited_once_with(
            messages.ADMIN_GIVE_KEY_COMPLETED_TEXT.format(
                key_id=1,
                member=target_member.full_name,
                telegram_user_id=200,
            ),
        )


class AddUserCommandTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.message = SimpleNamespace(reply_text=AsyncMock())
        self.update = SimpleNamespace(
            effective_message=self.message,
            effective_user=SimpleNamespace(id=100),
        )

    async def test_rejects_non_admin(self):
        with (
            patch(
                "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                return_value=build_member(100),
            ),
            patch("src.admin_command_handlers.add_gym_member") as add_member,
        ):
            await add_user_command_handler(
                self.update,
                SimpleNamespace(args=["200", "Ada", "Lovelace", "1234"]),
            )

        self.message.reply_text.assert_awaited_once_with(
            messages.ADMIN_COMMAND_FORBIDDEN_TEXT,
        )
        add_member.assert_not_called()

    async def test_rejects_wrong_argument_count(self):
        with (
            patch(
                "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                return_value=build_member(100, is_admin=True),
            ),
            patch("src.admin_command_handlers.add_gym_member") as add_member,
        ):
            for arguments in (
                ["200", "Ada", "Lovelace", "1234"],
                ["200", "Ada", "Lovelace", "1234", "@ada", "+49123"],
            ):
                with self.subTest(arguments=arguments):
                    await add_user_command_handler(
                        self.update,
                        SimpleNamespace(args=arguments),
                    )

        self.assertEqual(2, self.message.reply_text.await_count)
        self.message.reply_text.assert_has_awaits(
            [call(messages.ADMIN_ADD_USER_USAGE_TEXT)] * 2
        )
        add_member.assert_not_called()

    async def test_rejects_invalid_numeric_values(self):
        with (
            patch(
                "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                return_value=build_member(100, is_admin=True),
            ),
            patch("src.admin_command_handlers.add_gym_member") as add_member,
        ):
            await add_user_command_handler(
                self.update,
                SimpleNamespace(
                    args=["200", "Ada", "Lovelace", "not-a-room", "@ada"]
                ),
            )

        self.message.reply_text.assert_awaited_once_with(
            messages.ADMIN_BAD_VALUE_TEXT,
        )
        add_member.assert_not_called()

    async def test_reports_duplicate_telegram_user_id(self):
        with (
            patch(
                "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                return_value=build_member(100, is_admin=True),
            ),
            patch(
                "src.admin_command_handlers.add_gym_member",
                side_effect=GymMemberAlreadyExistsError,
            ),
        ):
            await add_user_command_handler(
                self.update,
                SimpleNamespace(args=["200", "Ada", "Lovelace", "1234", "@ada"]),
            )

        self.message.reply_text.assert_awaited_once_with(
            messages.ADMIN_ADD_USER_ALREADY_EXISTS_TEXT.format(
                telegram_user_id=200,
            ),
        )

    async def test_adds_user_with_required_telegram_name(self):
        member = GymMember(
            id=20,
            telegram_user_id=200,
            name="Ada",
            surname="Lovelace",
            room_number=1234,
            telegram_name="@ada",
            is_admin=False,
        )
        with (
            patch(
                "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                return_value=build_member(100, is_admin=True),
            ),
            patch("src.admin_command_handlers.add_gym_member", return_value=member) as add_member,
        ):
            await add_user_command_handler(
                self.update,
                SimpleNamespace(
                    args=["200", "Ada", "Lovelace", "1234", "@ada"],
                ),
            )

        add_member.assert_called_once_with(
            DATABASE_PATH,
            GymMember(telegram_user_id=200, name="Ada", surname="Lovelace", room_number=1234, telegram_name="@ada"),
        )
        self.message.reply_text.assert_awaited_once_with(
            messages.ADMIN_ADD_USER_COMPLETED_TEXT.format(
                member="Ada Lovelace",
                telegram_user_id=200,
                room_number=1234,
            ),
        )

    async def test_rejects_user_without_telegram_name(self):
        with (
            patch(
                "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                return_value=build_member(100, is_admin=True),
            ),
            patch("src.admin_command_handlers.add_gym_member") as add_member,
        ):
            await add_user_command_handler(
                self.update,
                SimpleNamespace(args=["200", "Ada", "Lovelace", "1234"]),
            )

        add_member.assert_not_called()
        self.message.reply_text.assert_awaited_once_with(
            messages.ADMIN_ADD_USER_USAGE_TEXT
        )


class UpdateUserArgumentTests(unittest.TestCase):
    def test_parses_options_in_any_order(self):
        member = parse_update_user_command_arguments(
            ["200", "-t", "@ada", "--room", "4321", "-n", "Ada"]
        )
        self.assertEqual(
            GymMember(telegram_user_id=200, telegram_name="@ada", room_number=4321, name="Ada"),
            member,
        )

    def test_rejects_unknown_duplicate_and_missing_options(self):
        invalid_arguments = (
            ["200", "--unknown", "value"],
            ["200", "--phone-number", "+49123"],
            ["200", "--name", "Ada", "--name", "Grace"],
            ["200", "-n", "Ada", "--name", "Grace"],
            ["200", "--name"],
            ["200", "--name", "--room"],
            ["200"],
        )

        for arguments in invalid_arguments:
            with self.subTest(arguments=arguments):
                with self.assertRaises(UpdateUserUsageError):
                    parse_update_user_command_arguments(arguments)

    def test_rejects_invalid_numeric_values(self):
        for arguments in (
            ["not-an-id", "--name", "Ada"],
            ["0", "--name", "Ada"],
            ["200", "--room", "not-a-room"],
            ["200", "--room", "0"],
        ):
            with self.subTest(arguments=arguments):
                with self.assertRaises(ValueError):
                    parse_update_user_command_arguments(arguments)

    def test_formats_only_actual_changes(self):
        member_before = build_member(200)
        member_after = GymMember(
            id=member_before.id,
            telegram_user_id=200,
            name="Ada",
            surname=member_before.surname,
            room_number=4321,
            telegram_name=member_before.telegram_name,
            is_admin=False,
        )

        self.assertEqual(
            "Name: Dima -> Ada\nRoom: 1234 -> 4321",
            format_gym_member_changes(member_before, member_after),
        )


class UpdateUserCommandTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.message = SimpleNamespace(reply_text=AsyncMock())
        self.update = SimpleNamespace(
            effective_message=self.message,
            effective_user=SimpleNamespace(id=100),
        )

    async def test_rejects_non_admin(self):
        with (
            patch(
                "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                return_value=build_member(100),
            ),
            patch("src.admin_command_handlers.update_gym_member") as update_member,
        ):
            await update_user_command_handler(
                self.update,
                SimpleNamespace(args=["200", "--name", "Ada"]),
            )

        self.message.reply_text.assert_awaited_once_with(
            messages.ADMIN_COMMAND_FORBIDDEN_TEXT,
        )
        update_member.assert_not_called()

    async def test_rejects_invalid_room_number(self):
        with (
            patch(
                "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                return_value=build_member(100, is_admin=True),
            ),
            patch("src.admin_command_handlers.update_gym_member") as update_member,
        ):
            await update_user_command_handler(
                self.update,
                SimpleNamespace(args=["200", "--room", "not-a-room"]),
            )

        self.message.reply_text.assert_awaited_once_with(messages.ADMIN_BAD_VALUE_TEXT)
        update_member.assert_not_called()

    async def test_rejects_malformed_options(self):
        with (
            patch(
                "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                return_value=build_member(100, is_admin=True),
            ),
            patch("src.admin_command_handlers.update_gym_member") as update_member,
        ):
            await update_user_command_handler(
                self.update,
                SimpleNamespace(args=["200", "--unknown", "value"]),
            )

        self.message.reply_text.assert_awaited_once_with(
            messages.ADMIN_UPDATE_USER_USAGE_TEXT,
        )
        update_member.assert_not_called()

    async def test_reports_missing_target_member(self):
        with (
            patch(
                "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                side_effect=[build_member(100, is_admin=True), None],
            ),
            patch("src.admin_command_handlers.update_gym_member") as update_member,
        ):
            await update_user_command_handler(
                self.update,
                SimpleNamespace(args=["200", "--name", "Ada"]),
            )

        self.message.reply_text.assert_awaited_once_with(
            messages.ADMIN_UPDATE_USER_NOT_FOUND_TEXT.format(telegram_user_id=200),
        )
        update_member.assert_not_called()

    async def test_updates_selected_fields_and_reports_actual_changes(self):
        member_before = build_member(200)
        member_after = GymMember(
            id=member_before.id,
            telegram_user_id=200,
            name="Ada",
            surname=member_before.surname,
            room_number=4321,
            telegram_name=member_before.telegram_name,
            is_admin=False,
        )
        with (
            patch(
                "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                side_effect=[build_member(100, is_admin=True), member_before],
            ),
            patch(
                "src.admin_command_handlers.update_gym_member",
                return_value=[member_after],
            ) as update_member,
        ):
            await update_user_command_handler(
                self.update,
                SimpleNamespace(
                    args=["200", "--room", "4321", "--name", "Ada"],
                ),
            )

        update_member.assert_called_once_with(
            DATABASE_PATH,
            GymMember(telegram_user_id=200, name="Ada", room_number=4321),
        )
        self.message.reply_text.assert_awaited_once_with(
            messages.ADMIN_UPDATE_USER_COMPLETED_TEXT.format(
                telegram_user_id=200,
                changes="\n".join(
                    (
                        "Name: Dima -> Ada",
                        "Room: 1234 -> 4321",
                    )
                ),
            )
        )

    async def test_reports_when_selected_value_does_not_change(self):
        target_member = build_member(200)
        with (
            patch(
                "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                side_effect=[build_member(100, is_admin=True), target_member],
            ),
            patch(
                "src.admin_command_handlers.update_gym_member",
                return_value=[target_member],
            ) as update_member,
        ):
            await update_user_command_handler(
                self.update,
                SimpleNamespace(args=["200", "--name", "Dima"]),
            )

        update_member.assert_called_once_with(
            DATABASE_PATH,
            GymMember(telegram_user_id=200, name="Dima"),
        )
        self.message.reply_text.assert_awaited_once_with(
            messages.ADMIN_UPDATE_USER_NO_CHANGES_TEXT.format(telegram_user_id=200),
        )


class UsersCommandTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.message = SimpleNamespace(reply_text=AsyncMock())
        self.update = SimpleNamespace(
            effective_message=self.message,
            effective_user=SimpleNamespace(id=100),
        )

    async def test_rejects_non_admin(self):
        with (
            patch(
                "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                return_value=build_member(100),
            ),
            patch("src.admin_command_handlers.query_gym_member_records") as get_members,
        ):
            await users_command_handler(self.update, SimpleNamespace(args=[]))

        self.message.reply_text.assert_awaited_once_with(
            messages.ADMIN_COMMAND_FORBIDDEN_TEXT,
        )
        get_members.assert_not_called()

    async def test_rejects_invalid_query(self):
        with (
            patch(
                "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                return_value=build_member(100, is_admin=True),
            ),
            patch("src.admin_command_handlers.query_gym_member_records") as get_members,
        ):
            await users_command_handler(
                self.update,
                SimpleNamespace(args=["Ada", "Lovelace", "not-a-room"]),
            )

        self.message.reply_text.assert_awaited_once_with(
            messages.ADMIN_USERS_USAGE_TEXT,
        )
        get_members.assert_not_called()

    async def test_reports_when_no_members_match(self):
        with (
            patch(
                "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                return_value=build_member(100, is_admin=True),
            ),
            patch(
                "src.admin_command_handlers.query_gym_member_records",
                return_value=[],
            ) as get_members,
        ):
            await users_command_handler(
                self.update,
                SimpleNamespace(args=["-n", "Ada", "-s", "Lovelace", "-r", "1234"]),
            )

        get_members.assert_called_once_with(
            DATABASE_PATH,
            GymMember(name="Ada", surname="Lovelace", room_number="1234"),
        )
        self.message.reply_text.assert_awaited_once_with(
            messages.ADMIN_USERS_NOT_FOUND_TEXT,
        )

    async def test_replies_with_complete_information_for_matching_members(self):
        members = [
            GymMember(
                id=20,
                telegram_user_id=200,
                name="Ada",
                surname="Lovelace",
                room_number=1234,
                telegram_name="@ada",
                is_admin=True,
            ),
            GymMember(
                id=21,
                telegram_user_id=201,
                name="Alan",
                surname="Turing",
                room_number=1235,
                telegram_name=None,
                is_admin=False,
            ),
        ]
        with (
            patch(
                "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                return_value=build_member(100, is_admin=True),
            ),
            patch(
                "src.admin_command_handlers.query_gym_member_records",
                return_value=members,
            ) as get_members,
        ):
            await users_command_handler(self.update, SimpleNamespace(args=[]))

        get_members.assert_called_once_with(
            DATABASE_PATH,
            GymMember(),
        )
        expected_reply = (
            "Name: Ada Lovelace\nRoom: 1234\nTelegram username: @ada\n"
            "Telegram ID: 200\nGym member ID: 20\nis admin: True\n"
            "Suspended until: None\nDeleted at: None\n----------\n"
            "Name: Alan Turing\nRoom: 1235\nTelegram username: None\n"
            "Telegram ID: 201\nGym member ID: 21\nis admin: False\n"
            "Suspended until: None\nDeleted at: None"
        )
        self.message.reply_text.assert_awaited_once_with(expected_reply)

    async def test_splits_large_results_between_telegram_messages(self):
        members = [
            GymMember(1, 100, "A" * 2500, "One", 1001, None, False),
            GymMember(2, 200, "B" * 2500, "Two", 1002, None, False),
        ]
        with (
            patch(
                "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                return_value=build_member(100, is_admin=True),
            ),
            patch("src.admin_command_handlers.query_gym_member_records", return_value=members),
        ):
            await users_command_handler(self.update, SimpleNamespace(args=[]))

        self.assertEqual(2, self.message.reply_text.await_count)
        for member, reply in zip(members, self.message.reply_text.await_args_list):
            text = reply.args[0]
            self.assertLessEqual(len(text), 4096)
            self.assertIn(f"Name: {member.full_name}\n", text)
            self.assertIn(f"Telegram ID: {member.telegram_user_id}\n", text)
            self.assertIn("is admin: False", text)


class KeyHistoryCommandTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.message = SimpleNamespace(reply_text=AsyncMock())
        self.update = SimpleNamespace(
            effective_message=self.message,
            effective_user=SimpleNamespace(id=100),
        )

    async def test_rejects_non_admin(self):
        with (
            patch(
                "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                return_value=build_member(100),
            ),
            patch("src.admin_command_handlers.get_key_history") as get_history,
        ):
            await key_history_command_handler(self.update, SimpleNamespace(args=[]))

        self.message.reply_text.assert_awaited_once_with(
            messages.ADMIN_COMMAND_FORBIDDEN_TEXT,
        )
        get_history.assert_not_called()

    async def test_rejects_missing_key_id(self):
        with (
            patch(
                "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                return_value=build_member(100, is_admin=True),
            ),
            patch("src.admin_command_handlers.get_key_history") as get_history,
        ):
            await key_history_command_handler(self.update, SimpleNamespace(args=[]))

        self.message.reply_text.assert_awaited_once_with(
            messages.ADMIN_KEY_HISTORY_USAGE_TEXT,
        )
        get_history.assert_not_called()

    async def test_uses_key_id_and_default_limit_and_replies_with_history(self):
        record = KeyHistoryRecord(
            event_id=1,
            key_id=2,
            member=build_member(200),
            taken_at=datetime(2026, 6, 5, 12, 30),
        )
        with (
            patch(
                "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                return_value=build_member(100, is_admin=True),
            ),
            patch(
                "src.admin_command_handlers.get_key_history",
                return_value=[record],
            ) as get_history,
        ):
            await key_history_command_handler(self.update, SimpleNamespace(args=["2"]))

        get_history.assert_called_once_with(DATABASE_PATH, 2, 5)
        self.message.reply_text.assert_awaited_once_with(
            process_key_history_records([record], "\n")[0],
        )

    async def test_filters_by_requested_key_with_default_limit(self):
        with (
            patch(
                "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                return_value=build_member(100, is_admin=True),
            ),
            patch(
                "src.admin_command_handlers.get_key_history",
                return_value=[],
            ) as get_history,
        ):
            await key_history_command_handler(
                self.update,
                SimpleNamespace(args=["10"]),
            )

        get_history.assert_called_once_with(DATABASE_PATH, 10, 5)
        self.message.reply_text.assert_awaited_once_with(
            messages.ADMIN_KEY_HISTORY_NOT_FOUND_TEXT,
        )

    async def test_filters_by_requested_key_and_uses_requested_limit(self):
        with (
            patch(
                "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                return_value=build_member(100, is_admin=True),
            ),
            patch(
                "src.admin_command_handlers.get_key_history",
                return_value=[],
            ) as get_history,
        ):
            await key_history_command_handler(
                self.update,
                SimpleNamespace(args=["2", "10"]),
            )

        get_history.assert_called_once_with(DATABASE_PATH, 2, 10)
        self.message.reply_text.assert_awaited_once_with(
            messages.ADMIN_KEY_HISTORY_NOT_FOUND_TEXT,
        )

    async def test_rejects_invalid_limit(self):
        with (
            patch(
                "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                return_value=build_member(100, is_admin=True),
            ),
            patch("src.admin_command_handlers.get_key_history") as get_history,
        ):
            await key_history_command_handler(
                self.update,
                SimpleNamespace(args=["0"]),
            )

        self.message.reply_text.assert_awaited_once_with(
            messages.ADMIN_BAD_VALUE_TEXT,
        )
        get_history.assert_not_called()


class KeyStatusCommandTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.message = SimpleNamespace(reply_text=AsyncMock())
        self.update = SimpleNamespace(
            effective_message=self.message,
            effective_user=SimpleNamespace(id=100),
        )

    async def test_rejects_non_admin(self):
        with (
            patch(
                "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                return_value=build_member(100),
            ),
            patch("src.admin_command_handlers.get_key_status") as get_status,
        ):
            await key_status_command_handler(self.update, SimpleNamespace(args=["1"]))

        self.message.reply_text.assert_awaited_once_with(
            messages.ADMIN_COMMAND_FORBIDDEN_TEXT,
        )
        get_status.assert_not_called()

    async def test_rejects_invalid_key_id(self):
        with (
            patch(
                "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                return_value=build_member(100, is_admin=True),
            ),
            patch("src.admin_command_handlers.get_key_status") as get_status,
        ):
            await key_status_command_handler(self.update, SimpleNamespace(args=["0"]))

        self.message.reply_text.assert_awaited_once_with(messages.ADMIN_BAD_VALUE_TEXT)
        get_status.assert_not_called()

    async def test_reports_missing_key(self):
        with (
            patch(
                "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                return_value=build_member(100, is_admin=True),
            ),
            patch("src.admin_command_handlers.get_key_status", return_value=(None, None, None)) as get_status,
        ):
            await key_status_command_handler(self.update, SimpleNamespace(args=["99"]))

        get_status.assert_called_once_with(DATABASE_PATH, 99)
        self.message.reply_text.assert_awaited_once_with(
            messages.KEY_NOT_FOUND_TEXT.format(key_id=99),
        )

    async def test_replies_with_complete_key_status(self):
        status = Key(
            key_id=1,
            current_holder_id=build_member(200).id,
            owner_member_id=20,
            is_active=True,
        )
        with (
            patch(
                "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                return_value=build_member(100, is_admin=True),
            ),
            patch("src.admin_command_handlers.get_key_status", return_value=(status, build_member(200), GymMember(20, 300, "Key", "Mailbox", 4321, None, False))),
        ):
            await key_status_command_handler(self.update, SimpleNamespace(args=["1"]))

        self.message.reply_text.assert_awaited_once_with(
            messages.key_status_text(status, build_member(200), GymMember(20, 300, "Key", "Mailbox", 4321, None, False)),
        )


class SetKeyActiveCommandTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.message = SimpleNamespace(reply_text=AsyncMock())
        self.update = SimpleNamespace(
            effective_message=self.message,
            effective_user=SimpleNamespace(id=100),
        )

    async def test_activate_rejects_non_admin(self):
        with (
            patch(
                "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                return_value=build_member(100),
            ),
            patch("src.admin_command_handlers.set_key_active") as set_active,
        ):
            await activate_key_command_handler(self.update, SimpleNamespace(args=["1"]))

        self.message.reply_text.assert_awaited_once_with(
            messages.ADMIN_COMMAND_FORBIDDEN_TEXT,
        )
        set_active.assert_not_called()

    async def test_deactivate_rejects_missing_key_id(self):
        with (
            patch(
                "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                return_value=build_member(100, is_admin=True),
            ),
            patch("src.admin_command_handlers.set_key_active") as set_active,
        ):
            await deactivate_key_command_handler(self.update, SimpleNamespace(args=[]))

        self.message.reply_text.assert_awaited_once_with(
            messages.ADMIN_DEACTIVATE_KEY_USAGE_TEXT,
        )
        set_active.assert_not_called()

    async def test_activate_reports_missing_key(self):
        with (
            patch(
                "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                return_value=build_member(100, is_admin=True),
            ),
            patch("src.admin_command_handlers.set_key_active", return_value=False) as set_active,
        ):
            await activate_key_command_handler(self.update, SimpleNamespace(args=["99"]))

        set_active.assert_called_once_with(DATABASE_PATH, 99, True)
        self.message.reply_text.assert_awaited_once_with(
            messages.KEY_NOT_FOUND_TEXT.format(key_id=99),
        )

    async def test_activate_sets_key_active(self):
        with (
            patch(
                "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                return_value=build_member(100, is_admin=True),
            ),
            patch("src.admin_command_handlers.set_key_active", return_value=True) as set_active,
        ):
            await activate_key_command_handler(self.update, SimpleNamespace(args=["2"]))

        set_active.assert_called_once_with(DATABASE_PATH, 2, True)
        self.message.reply_text.assert_awaited_once_with(
            messages.ADMIN_ACTIVATE_KEY_COMPLETED_TEXT.format(key_id=2),
        )

    async def test_deactivate_sets_key_inactive(self):
        with (
            patch(
                "src.admin_command_handlers.get_gym_member_by_telegram_user_id",
                return_value=build_member(100, is_admin=True),
            ),
            patch("src.admin_command_handlers.set_key_active", return_value=True) as set_active,
        ):
            await deactivate_key_command_handler(self.update, SimpleNamespace(args=["2"]))

        set_active.assert_called_once_with(DATABASE_PATH, 2, False)
        self.message.reply_text.assert_awaited_once_with(
            messages.ADMIN_DEACTIVATE_KEY_COMPLETED_TEXT.format(key_id=2),
        )


if __name__ == "__main__":
    unittest.main()
