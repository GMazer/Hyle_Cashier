from telegram import Update
from telegram.ext import ContextTypes
from config import ADMIN_ID
from core.database import db_get_all_chat_ids


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    msg = update.message.text.replace("/broadcast", "").strip()
    if not msg:
        return await update.message.reply_text("⚠️ Cú pháp: /broadcast <nội dung>")

    users = await db_get_all_chat_ids()
    ok = fail = 0
    for uid in users:
        if uid == ADMIN_ID:
            continue
        try:
            await context.bot.send_message(chat_id=uid, text=f"📢 **THÔNG BÁO:**\n\n{msg}", parse_mode="Markdown")
            ok += 1
        except:
            fail += 1

    await update.message.reply_text(f"✅ Gửi xong. OK={ok}, Fail={fail}")


async def report_issue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["awaiting_issue_report"] = True
    await update.message.reply_text(
        "🚨 **Báo lỗi / góp ý**\n\n"
        "Hãy nhập nội dung bạn muốn gửi cho admin.\n"
        "Ví dụ: bot không tạo được sổ, lỗi QR, hoặc thao tác nào bị kẹt."
        ,
        parse_mode="Markdown",
    )


async def submit_issue_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    report_text = update.message.text.strip()
    if not report_text:
        await update.message.reply_text("⚠️ Nội dung báo lỗi đang trống, hãy nhập lại giúp mình.")
        return

    user = update.effective_user
    chat = update.effective_chat
    current_book = context.user_data.get("current_book_name", "Chưa chọn sổ")

    admin_message = (
        "🚨 **BÁO LỖI TỪ USER**\n\n"
        f"👤 User: **{user.full_name}**\n"
        f"🆔 User ID: `{user.id}`\n"
        f"💬 Chat ID: `{chat.id}`\n"
        f"📂 Sổ hiện tại: **{current_book}**\n\n"
        f"📝 Nội dung:\n{report_text}"
    )

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=admin_message,
        parse_mode="Markdown",
    )
    await update.message.reply_text(
        "✅ Đã gửi báo lỗi tới admin. Cảm ơn bạn đã phản hồi!"
    )
