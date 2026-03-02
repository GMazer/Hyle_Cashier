import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from db import db_list_user_sheets
from sheets import get_google_client, ensure_sheet_total, format_vnd
from handlers.utils import require_sheet

async def list_books_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = await db_list_user_sheets(update.effective_user.id)
    if not rows:
        return await update.message.reply_text(
            "⚠️ Bạn chưa có sổ nào. Gửi link Google Sheet để kết nối trước nhé."
        )
    context.user_data["books"] = {r["sheet_id"]: r["sheet_title"] for r in rows}
    keyboard = [
        [InlineKeyboardButton(f"{i+1}. {r['sheet_title']}", callback_data=f"SELECT|{r['sheet_id']}")]
        for i, r in enumerate(rows)
    ]
    await update.message.reply_text("📂 Chọn sổ:", reply_markup=InlineKeyboardMarkup(keyboard))


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, bid = query.data.split("|")
    context.user_data["current_sheet_id"] = bid
    context.user_data["current_book_name"] = context.user_data.get("books", {}).get(bid, "Sổ đã chọn")
    await query.edit_message_text(f"✅ Đã chọn sổ: {context.user_data['current_book_name']}")


async def ls_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sid = await require_sheet(update, context)
    if not sid:
        return

    ws = get_google_client().open_by_key(sid).sheet1
    ensure_sheet_total(ws)

    total = ws.acell("G1", value_render_option="FORMATTED_VALUE").value
    if not total:
        total_raw = ws.acell("G1", value_render_option="UNFORMATTED_VALUE").value
        total = str(total_raw) if total_raw is not None else "0"

    rows = ws.get("A:D")
    if rows and rows[0] and rows[0][0].strip().lower() == "ngày":
        rows = rows[1:]

    data_rows = [r for r in rows if len(r) >= 3 and str(r[2]).strip()]
    last_5 = data_rows[-5:]

    def safe_get(r, i):
        return r[i].strip() if len(r) > i and r[i] else ""

    lines = []
    for r in last_5:
        day, item, money, note = safe_get(r,0), safe_get(r,1), safe_get(r,2), safe_get(r,3)
        lines.append(f"{day} | {item}: {format_vnd(money)}" + (f" | 📝 {note}" if note else ""))

    msg = "\n".join(lines) if lines else "Chưa có dữ liệu."
    await update.message.reply_text(f"🧾 5 dòng gần nhất:\n{msg}\n💰 TỔNG: {format_vnd(total)}")


async def new_book_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("⚠️ Hãy nhập tên sổ. VD: `/new AnSang`", parse_mode="Markdown")

    book_name = " ".join(context.args)
    await update.message.reply_text(f"⏳ Đang tạo sổ **{book_name}**...", parse_mode="Markdown")

    try:
        gc = get_google_client()
        if not gc:
            return await update.message.reply_text("❌ Lỗi kết nối Google.")

        sh = gc.create(book_name)
        sh.share(None, perm_type="anyone", role="writer")
        ws = sh.sheet1
        ws.update(range_name="A1:D1", values=[["Ngày", "Món", "Tiền", "Ghi chú"]])
        ws.update_acell("F1", "TỔNG NỢ:")
        ws.update_acell("G1", "=SUM(C:C)")
        ws.format("G1", {"textFormat": {"bold": True, "foregroundColor": {"red": 1.0}}})

        if "books" not in context.user_data:
            context.user_data["books"] = {}
        context.user_data["books"][sh.id] = book_name
        context.user_data["current_sheet_id"] = sh.id
        context.user_data["current_book_name"] = book_name

        await update.message.reply_text(
            f"✅ **Tạo sổ thành công!**\n📂 Tên: **{book_name}**\n🔗 [Xem Sheet]({sh.url})",
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
    except Exception as e:
        logging.error(f"Lỗi tạo sổ: {e}")
        await update.message.reply_text("⛔ Bot bị Google chặn tạo file.\n👉 Hãy tạo thủ công rồi gửi Link vào đây.")


async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sid = context.user_data.get("current_sheet_id")
    if not sid:
        return await update.message.reply_text("⚠️ Chưa kết nối sổ.")
    ws = get_google_client().open_by_key(sid).sheet1
    ws.batch_clear(["A2:D1000"])
    await update.message.reply_text("✅ Đã xóa trắng sổ nợ.")
