from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

BOT_ID= "t.me/api_test_4398523423043_bot"

def build_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("Request the key", callback_data="button_2"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

async def reply(update, context):
    await update.message.reply_text("Hello there!")

async def start(update, context):
    await update.message.reply_text(
        "Welcome! The buttons are ready.",
        reply_markup=build_keyboard(),
    )

async def replyButton(update, context):
    query = update.callback_query
    await query.answer("Button press received!")
    await query.message.reply_text(f"{query.data} is working.")

def main():
    """
    Handles the initial launch of the program (entry point).
    """
    token = "REMOVED_TELEGRAM_BOT_TOKEN"
    application = Application.builder().token(token).concurrent_updates(True).read_timeout(30).write_timeout(30).build()
    # application.add_handler(MessageHandler(filters.TEXT, reply)) # new text handler here
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(replyButton))
    print("Telegram Bot started!", flush=True)
    application.run_polling()

if __name__ == '__main__':
    main()
