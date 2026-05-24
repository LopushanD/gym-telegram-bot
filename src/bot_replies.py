from telegram import Message

from src import messages
from src.config import DEFAULT_DATABASE_PATH, DEFAULT_KEY_ID
from src.key_service import user_currently_holds_key
from src.keyboards import build_key_handover_holder_keyboard, build_start_keyboard


async def reply_with_start_state(
    message: Message,
    text: str = messages.START_STATE_TEXT,
    telegram_user_id: int | None = None,
) -> None:
    await message.reply_text(
        text,
        reply_markup=build_start_keyboard(
            include_holder_actions=user_currently_holds_key(
                DEFAULT_DATABASE_PATH,
                telegram_user_id,
                DEFAULT_KEY_ID,
            ),
        ),
    )


async def reply_with_holder_handover_cancel(
    message: Message,
    text: str = messages.START_STATE_TEXT,
    telegram_user_id: int | None = None,
) -> None:
    await message.reply_text(
        text,
        reply_markup=build_key_handover_holder_keyboard(),
    )
