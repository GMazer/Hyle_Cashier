import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from db import db_list_user_sheets, db_rename_sheet
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

    data = query.data

    # Xử lý chọn sổ để RENAME
    if data.startswith("RENAME_PICK|"):
        _, sid = data.split("|", 1)
        context.user_data["rename_sheet_id"] = sid
        old_name = context.user_data.get("books", {}).get(sid, sid)
        context.user_data["awaiting_rename"] = True
        await query.edit_message_text(
            f"✏️ Đang đổi tên sổ: **{old_name}**\n\nHãy nhập tên mới:",
            parse_mode="Markdown"
        )
        return

    # Xử lý chọn sổ thông thường
    _, bid = data.split("|", 1)
    context.user_data["current_sheet_id"] = bid
    book_name = context.user_data.get("books", {}).get(bid, "Sổ đã chọn")
    context.user_data["current_book_name"] = book_name
    await query.edit_message_text(
        f"✅ Đã chọn sổ: **{book_name}**\n\n"
        f"💳 Dùng /bankinfo để xem STK liên kết với sổ này\n"
        f"📲 Dùng /pay để tạo mã QR thanh toán",
        parse_mode="Markdown"
    )


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
    header_offset = 0
    if rows and rows[0] and rows[0][0].strip().lower() == "ngày":
        header_offset = 1
        rows = rows[1:]

    # Lưu index thật trên sheet (row 1-based, +1 header)
    data_rows = []
    for i, r in enumerate(rows):
        if len(r) >= 3 and str(r[2]).strip():
            sheet_row = i + 1 + header_offset  # row thật trên sheet (1-based)
            data_rows.append((sheet_row, r))

    last_5 = data_rows[-5:]

    def safe_get(r, i):
        return r[i].strip() if len(r) > i and r[i] else ""

    # Lưu mapping stt → sheet_row để /del dùng
    ls_map = {}
    lines = []
    for stt, (sheet_row, r) in enumerate(last_5, 1):
        day, item, money, note = safe_get(r,0), safe_get(r,1), safe_get(r,2), safe_get(r,3)
        lines.append(f"`{stt}.` {day} | {item}: {format_vnd(money)}" + (f" | 📝 {note}" if note else ""))
        ls_map[stt] = sheet_row

    context.user_data["ls_map"] = ls_map

    msg = "\n".join(lines) if lines else "Chưa có dữ liệu."
    await update.message.reply_text(
        f"🧾 5 dòng gần nhất:\n{msg}\n💰 TỔNG: {format_vnd(total)}\n\n"
        f"🗑 Xóa dòng: `/del <stt>` (VD: `/del 3`)",
        parse_mode="Markdown"
    )


async def del_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sid = await require_sheet(update, context)
    if not sid:
        return

    ls_map = context.user_data.get("ls_map", {})
    if not ls_map:
        return await update.message.reply_text("⚠️ Hãy dùng /ls trước để xem danh sách.")

    if not context.args:
        return await update.message.reply_text("⚠️ Cú pháp: `/del <stt>`\nVD: `/del 3`", parse_mode="Markdown")

    try:
        stt = int(context.args[0])
    except ValueError:
        return await update.message.reply_text("⚠️ STT phải là số. VD: `/del 2`", parse_mode="Markdown")

    sheet_row = ls_map.get(stt)
    if not sheet_row:
        return await update.message.reply_text(f"⚠️ Không tìm thấy dòng STT {stt}. Hãy /ls lại.")

    try:
        ws = get_google_client().open_by_key(sid).sheet1
        # Đọc dòng trước khi xóa để hiển thị
        row_data = ws.row_values(sheet_row)
        def safe_get(r, i):
            return r[i].strip() if len(r) > i and r[i] else ""
        day, item, money = safe_get(row_data,0), safe_get(row_data,1), safe_get(row_data,2)

        ws.delete_rows(sheet_row)

        # Clear mapping cũ vì row đã dịch
        context.user_data["ls_map"] = {}

        await update.message.reply_text(
            f"🗑 Đã xóa: {day} | {item}: {format_vnd(money)}\n"
            f"👉 Dùng /ls để xem lại danh sách."
        )
    except Exception as e:
        logging.error(f"Lỗi xóa dòng: {e}")
        await update.message.reply_text(f"⚠️ Lỗi xóa: {e}")


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


async def rename_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    rows = await db_list_user_sheets(uid)
    if not rows:
        return await update.message.reply_text("⚠️ Bạn chưa có sổ nào.")

    context.user_data["books"] = {r["sheet_id"]: r["sheet_title"] for r in rows}
    keyboard = [
        [InlineKeyboardButton(f"{i+1}. {r['sheet_title']}", callback_data=f"RENAME_PICK|{r['sheet_id']}")]
        for i, r in enumerate(rows)
    ]
    await update.message.reply_text(
        "✏️ Chọn sổ muốn đổi tên:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_rename_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Gọi từ message handler. Trả về True nếu đã xử lý rename, False nếu không."""
    if not context.user_data.get("awaiting_rename"):
        return False

    new_title = update.message.text.strip()
    sid = context.user_data.pop("rename_sheet_id", None)
    context.user_data.pop("awaiting_rename", None)

    if not sid or not new_title:
        await update.message.reply_text("⚠️ Đã hủy đổi tên.")
        return True

    ok = await db_rename_sheet(update.effective_user.id, sid, new_title)
    if ok:
        # Cập nhật cache
        if "books" in context.user_data:
            context.user_data["books"][sid] = new_title
        if context.user_data.get("current_sheet_id") == sid:
            context.user_data["current_book_name"] = new_title
        await update.message.reply_text(f"✅ Đã đổi tên sổ thành **{new_title}**", parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ Không tìm thấy sổ để đổi tên.")
    return True
