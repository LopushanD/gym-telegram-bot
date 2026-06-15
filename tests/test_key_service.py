import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.models import GymMember, KeyHolder
from src.key_service import (
    GiveKeyStatus,
    HandoverStatus,
    KeyReturnInstruction,
    give_key_to_member,
    get_keyholders,
    get_tracked_key_count,
    get_key_return_instruction,
    can_start_key_handover,
    user_currently_holds_key,
)


class KeyServiceTests(unittest.TestCase):
    def setUp(self):
        self.member = GymMember(
            id=10,
            telegram_user_id=123,
            name="Dima",
            surname="Ivanov",
            room_number=1234,
            telegram_name="@dima",
            phone_number="+49123456789",
            is_admin=False,
        )

    def test_get_keyholders_returns_domain_objects(self):
        with patch(
            "src.key_service.get_all_current_keyholders_info",
            return_value=[
                KeyHolder(
                    key_id=1,
                    member=GymMember(
                        id=10,
                        telegram_user_id=123,
                        name="Dima",
                        surname="Ivanov",
                        room_number=1234,
                        telegram_name="@dima",
                        phone_number="+49123456789",
                        is_admin=False,
                    ),
                )
            ],
        ):
            holders = get_keyholders("database.sqlite3")

        holder = holders[0]
        self.assertEqual(1, holder.key_id)
        self.assertEqual("Dima", holder.member.name)
        self.assertEqual("Ivanov", holder.member.surname)
        self.assertEqual(1234, holder.member.room_number)
        self.assertEqual("@dima", holder.member.telegram_name)
        self.assertEqual("+49123456789", holder.member.phone_number)

    def test_get_keyholders_returns_none_when_no_keys_exist(self):
        with patch("src.key_service.get_all_current_keyholders_info", return_value=[]):
            holder = get_keyholders("database.sqlite3")

        self.assertIsNone(holder)

    def test_get_tracked_key_count_returns_database_key_count(self):
        with patch("src.key_service.get_key_count", return_value=2) as get_key_count:
            key_count = get_tracked_key_count("database.sqlite3")

        self.assertEqual(2, key_count)
        get_key_count.assert_called_once_with("database.sqlite3")

    def test_get_key_return_instruction_returns_held_key_and_mailbox_room(self):
        with patch(
            "src.key_service.get_key_return_instruction_info",
            return_value=(2, 4321),
        ) as get_instruction:
            instruction = get_key_return_instruction("database.sqlite3", 123)

        self.assertEqual(KeyReturnInstruction(key_id=2, room_number=4321), instruction)
        get_instruction.assert_called_once_with("database.sqlite3", 123)

    def test_get_key_return_instruction_returns_none_when_user_holds_no_key(self):
        with patch("src.key_service.get_key_return_instruction_info", return_value=None):
            instruction = get_key_return_instruction("database.sqlite3", 123)

        self.assertIsNone(instruction)

    def test_get_key_return_instruction_returns_none_without_telegram_id(self):
        with patch("src.key_service.get_key_return_instruction_info") as get_instruction:
            instruction = get_key_return_instruction("database.sqlite3", None)

        self.assertIsNone(instruction)
        get_instruction.assert_not_called()

    def test_user_currently_holds_key_checks_holder_by_telegram_id(self):
        with patch(
            "src.key_service.get_current_keyholder_info",
            return_value=KeyHolder(
                key_id=1,
                member=GymMember(
                    id=10,
                    telegram_user_id=123,
                    name="Dima",
                    surname="Ivanov",
                    room_number=1234,
                    telegram_name="@dima",
                    phone_number="+49123456789",
                    is_admin=False,
                ),
            ),
        ) as get_current_keyholder_info:
            is_holder = user_currently_holds_key("database.sqlite3", 123, key_id=1)

        self.assertTrue(is_holder)
        get_current_keyholder_info.assert_called_once_with(
            "database.sqlite3",
            1,
            telegram_user_id=123,
        )

    def test_user_currently_holds_key_returns_false_without_telegram_id(self):
        with patch("src.key_service.get_current_keyholder_info") as get_current_keyholder_info:
            is_holder = user_currently_holds_key("database.sqlite3", None, key_id=1)

        self.assertFalse(is_holder)
        get_current_keyholder_info.assert_not_called()

    def test_start_key_handover_returns_ready_for_current_holder(self):
        with patch("src.key_service.user_currently_holds_key", return_value=True):
            result = can_start_key_handover("database.sqlite3", 123, key_id=1)

        self.assertEqual(HandoverStatus.READY, result.status)

    def test_start_key_handover_rejects_non_holder(self):
        with patch("src.key_service.user_currently_holds_key", return_value=False):
            result = can_start_key_handover("database.sqlite3", 123, key_id=1)

        self.assertEqual(HandoverStatus.NOT_CURRENT_HOLDER, result.status)

    def test_give_key_to_member_changes_holder(self):
        with (
            patch(
                "src.key_service.get_gym_member_by_telegram_user_id",
                return_value=self.member,
            ),
            patch("src.key_service.get_current_keyholder_info", return_value=object()),
            patch("src.key_service.change_key_holder") as change_key_holder,
        ):
            result = give_key_to_member("database.sqlite3", 1, 123)

        self.assertEqual(GiveKeyStatus.GIVEN, result.status)
        self.assertEqual(self.member, result.member)
        change_key_holder.assert_called_once_with("database.sqlite3", 1, self.member.id)

    def test_give_key_to_member_rejects_unregistered_member(self):
        with (
            patch(
                "src.key_service.get_gym_member_by_telegram_user_id",
                return_value=None,
            ),
            patch("src.key_service.get_current_keyholder_info") as get_holder,
            patch("src.key_service.change_key_holder") as change_key_holder,
        ):
            result = give_key_to_member("database.sqlite3", 1, 123)

        self.assertEqual(GiveKeyStatus.USER_NOT_REGISTERED, result.status)
        get_holder.assert_not_called()
        change_key_holder.assert_not_called()

    def test_give_key_to_member_rejects_missing_key(self):
        with (
            patch(
                "src.key_service.get_gym_member_by_telegram_user_id",
                return_value=self.member,
            ),
            patch("src.key_service.get_current_keyholder_info", return_value=None),
            patch("src.key_service.change_key_holder") as change_key_holder,
        ):
            result = give_key_to_member("database.sqlite3", 999, 123)

        self.assertEqual(GiveKeyStatus.KEY_NOT_FOUND, result.status)
        change_key_holder.assert_not_called()


if __name__ == "__main__":
    unittest.main()
