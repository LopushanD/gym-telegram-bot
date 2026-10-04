import os
from pathlib import Path
from typing import Final


DATABASE_PATH: Final[Path] = Path(
    os.environ.get("DATABASE_PATH", "data/gym_bot.sqlite3"))
TELEGRAM_MESSAGE_LIMIT = 4096
HANDOVER_WINDOW_SECONDS = 60
LAST_N_RECORDS_DEFAULT = 5
gym_member_record_separator = "\n"+"-"*10+"\n"
BOT_TOKEN: Final[str] = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CONTACT_NAME = os.environ.get("TELEGRAM_CONTACT_NAME")