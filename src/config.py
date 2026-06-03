import os
from pathlib import Path
from typing import Final


DEFAULT_DATABASE_PATH: Final[Path] = Path(
    os.environ.get("DATABASE_PATH", "gym_bot.sqlite3")
)
MAILBOX_MEMBER_ID: Final[int] = 1 #TODO REMOVE old code, used only in tests
HANDOVER_WINDOW_SECONDS = 30
BOT_ID: Final[str] = "t.me/api_test_4398523423043_bot"
BOT_TOKEN: Final[str] = os.environ.get(
    "TELEGRAM_BOT_TOKEN",
    "REMOVED_TELEGRAM_BOT_TOKEN",
)
