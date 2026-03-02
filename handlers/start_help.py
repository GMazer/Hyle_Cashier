from telegram import Update, BotCommand, MenuButtonCommands, BotCommandScopeChat
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from db import db_touch_user, db_get_user_sheet
from config import BOT_EMAIL

COMMANDS = [
    BotCommand("start", "Bắt đầu / Hướng dẫn kết nối"),
    BotCommand("help", "Xem cách ghi nợ & lệnh tắt"),
    BotCommand("ls", "Xem 5 khoản chi gần nhất"),
    BotCommand("so", "Menu chọn/đổi sổ"),
    BotCommand("pay", "Tạo mã QR thanh toán"),
    BotCommand("setbank", "Cài ngân hàng (VD: /setbank MB 123 TÊN)"),
    BotCommand("email", "Lấy Email Bot để cấp quyền"),
    BotCommand("new", "Tạo sổ mới"),
    BotCommand("done", "Chốt sổ (Xóa dữ liệu cũ)"),
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await db_touch_user(update.effective_user.id, update.effective_chat.id)

    # Auto-restore session từ DB
    if not context.user_data.get("current_sheet_id"):
        row = await db_get_user_sheet(update.effective_user.id)
        if row:
            context.user_data["current_sheet_id"] = row["sheet_id"]
            context.user_data["current_sheet_url"] = row["sheet_url"]
            context.user_data["books"] = {row["sheet_id"]: "Sổ đã kết nối"}
            context.user_data["current_book_name"] = "Sổ đã kết nối"

    chat_id = update.effective_chat.id
    await context.bot.set_my_commands(COMMANDS, scope=BotCommandScopeChat(chat_id))
    await context.bot.set_chat_menu_button(chat_id=chat_id, menu_button=MenuButtonCommands())

    user_name = update.effective_user.full_name
    books = context.user_data.get("books", {})
    current_book = context.user_data.get("current_book_name", "Chưa chọn")

    if books:
        msg = (
            f"👋 **Xin chào {user_name}!**\n\n"
            f"📂 Sổ hiện tại: **{current_book}**\n\n"
            "💵 **Ghi nợ nhanh:**\n"
            "   `Banh mi 20` (Hôm nay)\n"
            "   `30/1 Pho 40` (Ngày cũ)\n\n"
            "⚙️ **Lệnh tắt:** /ls, /so, /pay, /help"
        )
    else:
        msg = (
            f"👋 **Chào mừng {user_name} đến với Bot Ghi Nợ Ăn Sáng!**\n\n"
            f"1️⃣ Share quyền Editor cho: `{BOT_EMAIL}`\n"
            f"2️⃣ Gửi Link Sheet vào đây để kết nối."
        )

    await update.message.reply_text(msg, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ **Bước 1:** Share quyền **Editor** cho email bot:\n"
        f"`{BOT_EMAIL}`",
        parse_mode=ParseMode.MARKDOWN
    )
    await update.message.reply_text(
        "✅ **Bước 2:** Gửi **link Google Sheet** vào đây.\n\n"
        "Ví dụ:\n`https://docs.google.com/spreadsheets/d/...`",
        parse_mode=ParseMode.MARKDOWN
    )
    await update.message.reply_text(
        "💵 **Ghi nợ nhanh:**\n"
        "• Hôm nay: `Banh mi 20`\n"
        "• Ngày cũ: `30/01 Pho 40`\n\n"
        "📂 **Quản lý sổ:** `/so` | `/new` | `/ls`\n"
        "🏦 **Ngân hàng:** `/setbank MB 0123456789 TEN` → `/pay`\n"
        "🧾 **Khác:** `/email` | `/done` | `/start`",
        parse_mode=ParseMode.MARKDOWN
    )


async def email_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"📧 Email Bot:\n`{BOT_EMAIL}`", parse_mode="Markdown")
