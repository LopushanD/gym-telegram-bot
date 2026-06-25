import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.admin_commands import (
    ACTIVATE_KEY_ADMIN_COMMAND,
    ADD_USER_ADMIN_COMMAND,
    DEACTIVATE_KEY_ADMIN_COMMAND,
    GIVE_KEY_ADMIN_COMMAND,
    SHOW_KEY_HISTORY_ADMIN_COMMAND,
    SHOW_KEY_STATUS_ADMIN_COMMAND,
    SHOW_USERS_ADMIN_COMMAND,
    UPDATE_USER_ADMIN_COMMAND,
    load_command_documentation,
)


class AdminCommandDocumentationTests(unittest.TestCase):
    def test_each_admin_command_has_command_specific_documentation(self):
        command_names = (
            ADD_USER_ADMIN_COMMAND,
            UPDATE_USER_ADMIN_COMMAND,
            GIVE_KEY_ADMIN_COMMAND,
            SHOW_USERS_ADMIN_COMMAND,
            SHOW_KEY_HISTORY_ADMIN_COMMAND,
            SHOW_KEY_STATUS_ADMIN_COMMAND,
            ACTIVATE_KEY_ADMIN_COMMAND,
            DEACTIVATE_KEY_ADMIN_COMMAND,
        )

        for command_name in command_names:
            with self.subTest(command_name=command_name):
                documentation = load_command_documentation(command_name)

                self.assertIn(f"`/{command_name}", documentation)
                self.assertIn("*Usage*", documentation)
                self.assertRegex(documentation, r"\*Examples?\*")


if __name__ == "__main__":
    unittest.main()
