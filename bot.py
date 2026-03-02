import os
import logging
from telegram import BotCommand, MenuButtonCommands, BotCommandScopeDefault
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, PicklePersistence,
)

from config import TOKEN
from db import db_init
from handlers.start_help import start, help_command, email_command, COMMANDS
from handlers.books import list_books_command, button_callback, ls_command, new_book_command, done_command
from handlers.bank import set_bank_command, pay_command
from handlers.message import handle_message
from handlers.admin import broadcast_command

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

async def post_init(application):
    await db_init()
    await application.bot.set_my_commands(COMMANDS, scope=BotCommandScopeDefault())
    await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    print("✅ Bot đã khởi động")

if __name__ == "__main__":
    persistence = PicklePersistence(filepath="bot_persistence.pkl")

    application = (
        ApplicationBuilder()
        .token(TOKEN)
        .persistence(persistence)
        .post_init(post_init)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("email", email_command))
    application.add_handler(CommandHandler("ls", ls_command))
    application.add_handler(CommandHandler("so", list_books_command))
    application.add_handler(CommandHandler("new", new_book_command))
    application.add_handler(CommandHandler("done", done_command))
    application.add_handler(CommandHandler("setbank", set_bank_command))
    application.add_handler(CommandHandler("pay", pay_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL")
    PORT = int(os.environ.get("PORT", "8443"))

    if WEBHOOK_URL:
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{TOKEN}",
        )
    else:
        application.run_polling()