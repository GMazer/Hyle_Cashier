from telegram import Update, BotCommand, MenuButtonCommands, BotCommandScopeChat
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from core.database import db_touch_user
from handlers.menu import get_menu

COMMANDS = [
    BotCommand("start",    "🏠 Bắt đầu"),
    BotCommand("help",     "📖 Hướng dẫn sử dụng"),
    BotCommand("ls",       "🧾 Xem chi tiêu gần nhất"),
    BotCommand("del",      "🗑 Xóa dòng (VD: /del 3)"),
    BotCommand("so",       "📂 Chọn / đổi sổ"),
    BotCommand("new",      "➕ Tạo sổ mới"),
    BotCommand("rename",   "✏️ Đổi tên sổ"),
    BotCommand("done",     "🗑 Chốt sổ – xóa dữ liệu cũ"),
    BotCommand("setbank",  "🏦 Cài ngân hàng"),
    BotCommand("bankinfo", "💳 Xem thông tin ngân hàng"),
    BotCommand("pay",      "📲 Tạo mã QR thanh toán"),
    BotCommand("delbook",  "🗑 Xóa sổ (vĩnh viễn)"),
    BotCommand("report",   "🚨 Báo lỗi / góp ý"),
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await db_touch_user(update.effective_user.id, update.effective_chat.id)

    # Auto-restore session từ DB
    if not context.user_data.get("current_sheet_id"):
        from core.database import db_list_user_sheets
        sheets = await db_list_user_sheets(update.effective_user.id)
        if sheets:
            context.user_data["books"] = {r["sheet_id"]: r["sheet_title"] for r in sheets}
            latest = sheets[0]
            context.user_data["current_sheet_id"] = latest["sheet_id"]
            context.user_data["current_sheet_url"] = latest["sheet_url"]
            context.user_data["current_book_name"] = latest["sheet_title"]

    chat_id = update.effective_chat.id
    await context.bot.set_my_commands(COMMANDS, scope=BotCommandScopeChat(chat_id))
    await context.bot.set_chat_menu_button(chat_id=chat_id, menu_button=MenuButtonCommands())

    user_name = update.effective_user.full_name
    books = context.user_data.get("books", {})
    current_book = context.user_data.get("current_book_name", "Chưa chọn")
    menu = get_menu(context)

    if books:
        msg = (
            f"👋 **Xin chào {user_name}!**\n\n"
            f"📂 Sổ hiện tại: **{current_book}**\n\n"
            "💵 **Ghi chi tiêu nhanh:**\n"
            "   `Banh mi 20` → hôm nay\n"
            "   `30/1 Pho 40` → ngày cũ\n"
            "   `Cafe 25\\nBanh mi 20\\nGui xe 5` → nhiều khoản / 1 tin nhắn\n\n"
            "👇 Dùng menu bên dưới để thao tác."
        )
    else:
        msg = (
            f"👋 **Chào mừng {user_name}!**\n\n"
            "Mình là Bot Ghi Nợ Ăn Sáng 🍜\n"
            "Giúp bạn ghi chép chi tiêu nhóm dễ dàng!\n\n"
            "👇 Bấm **➕ Tạo sổ** để bắt đầu,\n"
            "hoặc **🚨 Báo lỗi** nếu cần hỗ trợ."
        )

    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=menu)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    menu = get_menu(context)
    await update.message.reply_text(
        "📖 **Hướng dẫn sử dụng**\n\n"
        "**1️⃣ Tạo sổ mới**\n"
        "Bấm **➕ Tạo sổ** → nhập tên → xong!\n\n"
        "**2️⃣ Ghi chi tiêu**\n"
        "Gõ trực tiếp, VD:\n"
        "• `Banh mi 20` → 20,000đ hôm nay\n"
        "• `30/1 Pho 40` → 40,000đ ngày 30/01\n"
        "• `Com tam 35 ngon` → kèm ghi chú\n"
        "• Có thể nhập **nhiều khoản trong 1 tin nhắn**, mỗi dòng 1 khoản:\n"
        "  `Cafe 25\\nBanh mi 20\\nGui xe 5`\n\n"
        "**3️⃣ Xem & xóa**\n"
        "• 🧾 **Xem nợ** → 5 dòng gần nhất + tổng\n"
        "• `/del 3` → xóa dòng thứ 3\n\n"
        "**4️⃣ Thanh toán**\n"
        "• 💳 **Ngân hàng** → cài STK\n"
        "• 📲 **Thanh toán** → tạo mã QR\n\n"
        "**5️⃣ Quản lý sổ**\n"
        "• 📂 **Chọn sổ** → đổi sổ đang dùng\n"
        "• `/rename` → đổi tên sổ\n"
        "• `/delbook` → xóa sổ vĩnh viễn\n"
        "• `/done` → xóa trắng dữ liệu\n\n"
        "**6️⃣ Báo lỗi / góp ý**\n"
        "• Bấm **🚨 Báo lỗi** trong menu\n"
        "• Hoặc dùng `/report` để gửi tin nhắn cho admin",
        parse_mode="Markdown",
        reply_markup=menu
    )
