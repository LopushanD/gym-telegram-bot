import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src import admin_command_handlers
from src.database import database_connection, initialize_database


class GiveKeyMailboxIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_command_records_destination_and_preserves_owner_and_history(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        path = Path(directory) / "keys.sqlite3"
        initialize_database(path)
        with database_connection(path) as connection:
            connection.executemany(
                """INSERT INTO gym_members (id, telegram_user_id, name, surname, room_number, is_admin)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [(1, 100, "Ada", "Owner", 101, 1), (2, 200, "Alex", "Recipient", 202, 0)],
            )
            connection.execute(
                """INSERT INTO keys (id, name, current_holder_id, owner_member_id, is_in_mailbox)
                   VALUES (1, 'Red', 1, 1, 1)"""
            )

        message = SimpleNamespace(reply_text=AsyncMock())
        update = SimpleNamespace(effective_message=message, effective_user=SimpleNamespace(id=100))
        cases = (
            (["1", "100"], (1, 1, 0), "was given to Ada Owner"),
            (["1", "200", "-m", "True"], (2, 1, 1), "Alex Recipient's mailbox"),
            (["1", "200", "--mailbox", "False"], (2, 1, 0), "was given to Alex Recipient"),
            (["1", "100", "--mailbox", "True"], (1, 1, 1), "Ada Owner's mailbox"),
            (["1", "100"], (1, 1, 0), "was given to Ada Owner"),
        )
        with (
            patch.object(admin_command_handlers, "DATABASE_PATH", path),
            patch.object(admin_command_handlers, "cancel_pending_handover") as cancel_handover,
        ):
            for arguments, expected_state, expected_reply in cases:
                with self.subTest(arguments=arguments):
                    message.reply_text.reset_mock()
                    await admin_command_handlers.give_key_command_handler(
                        update, SimpleNamespace(args=arguments)
                    )
                    with database_connection(path) as connection:
                        state = connection.execute(
                            "SELECT current_holder_id, owner_member_id, is_in_mailbox FROM keys WHERE id = 1"
                        ).fetchone()
                    self.assertEqual(expected_state, state)
                    message.reply_text.assert_awaited_once()
                    self.assertIn("key 1 (Red)", message.reply_text.await_args.args[0])
                    self.assertIn(expected_reply, message.reply_text.await_args.args[0])
            self.assertEqual(len(cases), cancel_handover.call_count)

        with database_connection(path) as connection:
            history = connection.execute(
                "SELECT key_id, holder_id FROM key_holder_history ORDER BY event_id"
            ).fetchall()
        self.assertEqual([(1, 1), (1, 2), (1, 2), (1, 1), (1, 1)], history)
