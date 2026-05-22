from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from database import DEFAULT_DATABASE_PATH, get_current_key_holder, initialize_database

BOT_ID= "t.me/api_test_4398523423043_bot"
KEY_REQUEST_CALLBACK = "key_request"
KEY_OBTAINED_CALLBACK = "key_obtained"


def build_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("Request the key", callback_data=KEY_REQUEST_CALLBACK)
        ],
        [
            InlineKeyboardButton("Got the key", callback_data=KEY_OBTAINED_CALLBACK)
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return

    await update.message.reply_text(
        "Welcome! The buttons are ready.",
        reply_markup=build_keyboard(),
    )

async def request_key_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return

    if query.data == KEY_REQUEST_CALLBACK:
        await handle_key_request(update, context)
        return

    if query.data == KEY_OBTAINED_CALLBACK:
        await handle_key_obtained(update, context)
        return

    await query.answer("Unknown button.")


async def handle_key_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.message is None:
        return

    holder = get_current_key_holder(DEFAULT_DATABASE_PATH)

    await query.answer("Looking up the key holder...")
    if holder is None:
        await query.message.reply_text("No key is registered in the database yet.")
        return

    name, surname, room_number = holder
    await query.message.reply_text(
        f"The key is currently held by {name} {surname}, room {room_number}."
    )


async def handle_key_obtained(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.message is None:
        return

    await query.answer("Key status received.")
    await query.message.reply_text("Got it. The key-obtained button is working.")


def main() -> None:
    """
    Handles the initial launch of the program (entry point).
    """
    token = "REMOVED_TELEGRAM_BOT_TOKEN"
    initialize_database(DEFAULT_DATABASE_PATH)
    application = Application.builder().token(token).concurrent_updates(True).read_timeout(30).write_timeout(30).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(request_key_handler))
    print("Telegram Bot started!", flush=True)
    application.run_polling()

if __name__ == '__main__':
    main()
