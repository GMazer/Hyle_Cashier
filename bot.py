import os
import logging
from contextlib import asynccontextmanager

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from telegram import BotCommand, MenuButtonCommands, BotCommandScopeDefault, Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, PicklePersistence,
)

from config import TOKEN
from core.database import db_init
from handlers.start_help import start, help_command, COMMANDS
from handlers.books import (
    list_books_command, button_callback, ls_command,
    del_command, new_book_command, done_command, rename_command,
    delbook_command,
)
from handlers.bank import set_bank_command, pay_command, bank_info_command, bank_callback
from handlers.message import handle_message
from handlers.admin import broadcast_command, report_issue_command

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


def _register_handlers(app):
    """Register all command / message handlers on *app*."""
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("ls", ls_command))
    app.add_handler(CommandHandler("del", del_command))
    app.add_handler(CommandHandler("so", list_books_command))
    app.add_handler(CommandHandler("new", new_book_command))
    app.add_handler(CommandHandler("rename", rename_command))
    app.add_handler(CommandHandler("done", done_command))
    app.add_handler(CommandHandler("setbank", set_bank_command))
    app.add_handler(CommandHandler("pay", pay_command))
    app.add_handler(CommandHandler("bankinfo", bank_info_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("report", report_issue_command))
    app.add_handler(CommandHandler("delbook", delbook_command))
    app.add_handler(CallbackQueryHandler(bank_callback, pattern=r"^BANK_"))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))


async def _common_post_init(app):
    """Shared init: DB + bot commands."""
    await db_init()
    await app.bot.set_my_commands(COMMANDS, scope=BotCommandScopeDefault())
    await app.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    print("✅ Bot đã khởi động")


# ---------------------------------------------------------------------------
# Webhook mode  (Render / production)
# ---------------------------------------------------------------------------

def _build_webhook_app():
    """Build a PTB Application without updater (manual webhook)."""
    persistence = PicklePersistence(filepath="bot_persistence.pkl")
    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .persistence(persistence)
        .updater(None)
        .build()
    )
    _register_handlers(app)
    return app


ptb_app = _build_webhook_app()


async def health_check(request: Request) -> PlainTextResponse:
    """Health-check endpoint for UptimeRobot  →  GET /"""
    return PlainTextResponse("OK")


async def telegram_webhook(request: Request) -> PlainTextResponse:
    """Receive Telegram updates  →  POST /{TOKEN}"""
    update = Update.de_json(await request.json(), ptb_app.bot)
    await ptb_app.process_update(update)
    return PlainTextResponse("OK")


@asynccontextmanager
async def lifespan(_app: Starlette):
    # ── startup ──
    await ptb_app.initialize()
    await _common_post_init(ptb_app)

    webhook_url = os.environ.get("RENDER_EXTERNAL_URL", "")
    if webhook_url:
        await ptb_app.bot.set_webhook(url=f"{webhook_url}/{TOKEN}")

    await ptb_app.start()

    yield

    # ── shutdown ──
    await ptb_app.stop()
    await ptb_app.shutdown()


starlette_app = Starlette(
    routes=[
        Route("/", health_check, methods=["GET", "HEAD"]),
        Route(f"/{TOKEN}", telegram_webhook, methods=["POST"]),
    ],
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL")
    PORT = int(os.environ.get("PORT", "8443"))

    if WEBHOOK_URL:
        # Production on Render: webhook via Starlette + uvicorn
        uvicorn.run(starlette_app, host="0.0.0.0", port=PORT)
    else:
        # Local development: long-polling
        persistence = PicklePersistence(filepath="bot_persistence.pkl")
        app = (
            ApplicationBuilder()
            .token(TOKEN)
            .persistence(persistence)
            .post_init(_common_post_init)
            .build()
        )
        _register_handlers(app)
        app.run_polling()