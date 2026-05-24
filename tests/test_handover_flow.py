import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src import handover_flow


class HandoverFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self):
        for pending_handover in handover_flow.PENDING_HANDOVERS.values():
            pending_handover.timeout_task.cancel()
        handover_flow.PENDING_HANDOVERS.clear()

    async def test_complete_handover_sends_one_button_message_in_same_chat(self):
        state_change_function = AsyncMock()
        pending_message = SimpleNamespace(chat_id=10)
        confirmation_message = SimpleNamespace(chat_id=10)
        pending_handover = handover_flow.PendingHandover(
            holder_user_id=123,
            holder_display_name="Member One",
            message=pending_message,
            state_change_function=state_change_function,
            timeout_task=asyncio.create_task(asyncio.sleep(60)),
        )
        handover_flow.PENDING_HANDOVERS[1] = pending_handover
        query = SimpleNamespace(
            message=confirmation_message,
            from_user=SimpleNamespace(
                id=456,
                full_name="Member Two",
                username=None,
            ),
        )

        with patch.object(handover_flow, "change_key_holder") as change_key_holder:
            await handover_flow.complete_handover_interaction(
                member_id=2,
                key_id=1,
                query=query,
                pending_handover=pending_handover,
            )

        change_key_holder.assert_called_once_with(
            handover_flow.DEFAULT_DATABASE_PATH,
            1,
            2,
        )
        state_change_function.assert_awaited_once_with(
            pending_message,
            "The key was handed over from Member One to Member Two.",
            123,
        )
        await asyncio.sleep(0)
        self.assertTrue(pending_handover.timeout_task.cancelled())
        self.assertNotIn(1, handover_flow.PENDING_HANDOVERS)


if __name__ == "__main__":
    unittest.main()
