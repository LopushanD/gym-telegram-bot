from telegram import Message

from src import messages
from src.config import DEFAULT_DATABASE_PATH
from src.key_service import user_currently_holds_key,user_currently_holds_any_key
from src.keyboards import build_key_handover_holder_keyboard, build_start_keyboard


def _build_start_state_markup(telegram_user_id: int | None = None):
    return build_start_keyboard(
        include_holder_actions=user_currently_holds_any_key(
            DEFAULT_DATABASE_PATH,
            telegram_user_id,
        )
    )

async def reply_with_start_state(
    message: Message,
    text: str = messages.START_USER_MENU_TEXT,
    telegram_user_id: int | None = None,
) -> None:
    """creates new message (not edits the old one) with start state"""
    await message.reply_text(
        text,
        reply_markup=_build_start_state_markup(telegram_user_id),
    )

async def edit_to_start_state(
    message: Message,
    text: str = messages.START_USER_MENU_TEXT,
    telegram_user_id: int | None = None,
) -> None:
    await message.edit_text(
        text,
        reply_markup=_build_start_state_markup(telegram_user_id),
    )

async def edit_to_holder_handover_cancel(
    message: Message,
    text: str = messages.START_USER_MENU_TEXT,
    telegram_user_id: int | None = None,
) -> None:
    await message.edit_text(
        text,
        reply_markup=build_key_handover_holder_keyboard(),
    )
