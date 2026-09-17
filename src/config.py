import os
from pathlib import Path
from typing import Final


DEFAULT_DATABASE_PATH: Final[Path] = Path(
    os.environ.get("DATABASE_PATH", "data/gym_bot.sqlite3")
)
TELEGRAM_MESSAGE_LIMIT = 4096
MAILBOX_MEMBER_ID: Final[int] = 1 #TODO REMOVE old code, used only in tests
HANDOVER_WINDOW_SECONDS = 30
LAST_N_RECORDS_DEFAULT = 5
BOT_TOKEN: Final[str] = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CONTACT_NAME = os.environ.get("TELEGRAM_CONTACT_NAME")