import re
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from db import db_touch_user, db_upsert_user_sheet
from sheets import get_google_client, ensure_sheet_total, format_vnd
from handlers.utils import require_sheet

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await db_touch_user(update.effective_user.id, update.effective_chat.id)
    text = update.message.text.strip()

    # Nhận Link Sheet
    if "docs.google.com" in text:
        try:
            sh = get_google_client().open_by_url(text)
            sheet_id = sh.id
            sheet_title = sh.title

            if "books" not in context.user_data:
                context.user_data["books"] = {}
            context.user_data["books"][sheet_id] = sheet_title
            context.user_data["current_sheet_id"] = sheet_id
            context.user_data["current_book_name"] = sheet_title

            await db_upsert_user_sheet(
                update.effective_user.id,
                update.effective_chat.id,
                text.strip(),
                sheet_id,
                sheet_title,
            )
            await update.message.reply_text(f"✅ Đã kết nối sổ: {sheet_title}")
        except Exception as e:
            logging.error(f"Sheet error: {e}")
            await update.message.reply_text(f"❌ Sheet error: {e}")
        return

    # Ghi nợ
    sid = await require_sheet(update, context)
    if not sid:
        return

    try:
        ws = get_google_client().open_by_key(sid).sheet1
        ensure_sheet_total(ws)

        m = re.search(r"\d+(\.\d+)?", text)
        if not m:
            return

        amount = float(m.group()) * 1000
        start, end = m.span()
        item = text[:start].strip()
        note = text[end:].strip()

        next_row = len(ws.col_values(1)) + 1
        ws.update(f"A{next_row}:D{next_row}", [[
            datetime.now().strftime("%d/%m/%Y"),
            item,
            amount,
            note,
        ]])

       # sau khi ws.update(...) xong
        total = ws.acell("G1", value_render_option="FORMATTED_VALUE").value
        if not total:
            total_raw = ws.acell("G1", value_render_option="UNFORMATTED_VALUE").value
            total = total_raw if total_raw is not None else 0

        await update.message.reply_text(
            f"✅ Ghi: {item} ({format_vnd(amount)})\n"
            f"📝 Ghi chú: {note if note else '—'}\n"
            f"💰 Tổng: {format_vnd(total)}"
        )
    except Exception as e:
        logging.error(f"Ghi nợ lỗi: {e}")
        await update.message.reply_text(f"⚠️ Lỗi ghi nợ: {e}")
