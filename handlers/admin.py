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
