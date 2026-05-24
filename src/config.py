import os
from pathlib import Path
from typing import Final


DEFAULT_DATABASE_PATH: Final[Path] = Path("gym_bot.sqlite3")
DEFAULT_KEY_ID: Final[int] = 1
MAILBOX_MEMBER_ID: Final[int] = 1
HANDOVER_WINDOW_SECONDS = 30
BOT_ID: Final[str] = "t.me/api_test_4398523423043_bot"
BOT_TOKEN: Final[str] = os.environ.get(
    "TELEGRAM_BOT_TOKEN",
    "REMOVED_TELEGRAM_BOT_TOKEN",
)
