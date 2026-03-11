import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from core.database import db_list_user_sheets, db_rename_sheet, db_delete_user_sheet, db_upsert_user_sheet
from core.sheets import get_google_client, ensure_sheet_total, format_vnd
from config import DRIVE_FOLDER_ID
from handlers.utils import require_sheet
from handlers.menu import get_menu, MENU_CONNECTED

async def list_books_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = await db_list_user_sheets(update.effective_user.id)
    if not rows:
        return await update.message.reply_text(
            "⚠️ Bạn chưa có sổ nào.\n\n"
            "👉 **Cách thêm sổ:**\n"
            "1️⃣ Tạo mới: `/new <tên sổ>` (VD: `/new AnSang`)\n"
            "2️⃣ Hoặc gửi link Google Sheet có sẵn vào đây.",
            parse_mode="Markdown"
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

    # Xử lý chọn sổ để XÓA
    if data.startswith("DELBOOK_PICK|"):
        _, sid = data.split("|", 1)
        book_name = context.user_data.get("books", {}).get(sid, sid)
        keyboard = [
            [
                InlineKeyboardButton("✅ Xác nhận xóa", callback_data=f"DELBOOK_CONFIRM|{sid}"),
                InlineKeyboardButton("❌ Hủy", callback_data="DELBOOK_CANCEL"),
            ]
        ]
        await query.edit_message_text(
            f"⚠️ **Bạn có chắc muốn xóa sổ \"{book_name}\"?**\n\n"
            "🗑 Sổ sẽ bị xóa **vĩnh viễn** khỏi Google Drive!\n"
            "Dữ liệu trong sổ sẽ **không thể khôi phục**.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    # Xác nhận xóa sổ
    if data.startswith("DELBOOK_CONFIRM|"):
        _, sid = data.split("|", 1)
        book_name = context.user_data.get("books", {}).get(sid, sid)
        try:
            gc = get_google_client()
            if gc:
                gc.del_spreadsheet(sid)
            uid = update.effective_user.id
            await db_delete_user_sheet(uid, sid)

            # Xóa khỏi cache
            if "books" in context.user_data:
                context.user_data["books"].pop(sid, None)
            if context.user_data.get("current_sheet_id") == sid:
                context.user_data.pop("current_sheet_id", None)
                context.user_data.pop("current_book_name", None)

            await query.edit_message_text(
                f"🗑 Đã xóa sổ **{book_name}** thành công!",
                parse_mode="Markdown"
            )
        except Exception as e:
            logging.error(f"Lỗi xóa sổ: {e}")
            await query.edit_message_text(
                f"❌ Không xóa được sổ.\n\n"
                f"🔍 Lỗi: `{e}`",
                parse_mode="Markdown"
            )
        return

    # Hủy xóa sổ
    if data == "DELBOOK_CANCEL":
        await query.edit_message_text("✅ Đã hủy xóa sổ.")
        return

    # Xử lý chọn sổ thông thường
    _, bid = data.split("|", 1)
    context.user_data["current_sheet_id"] = bid
    book_name = context.user_data.get("books", {}).get(bid, "Sổ đã chọn")
    context.user_data["current_book_name"] = book_name
    await query.edit_message_text(
        f"✅ Đã chọn sổ: **{book_name}**\n\n"
        f"💵 Ghi nợ nhanh: `Banh mi 20`\n"
        f"🧾 Xem nợ: /ls\n"
        f"📲 Thanh toán: /pay\n"
        f"💳 Xem STK: /bankinfo\n\n"
        f"👇 Hoặc dùng menu bên dưới.",
        parse_mode="Markdown"
    )
    # Gửi thêm 1 tin nhắn ngắn kèm reply_markup để cập nhật menu
    await query.message.reply_text(
        f"📂 Sổ hiện tại: **{book_name}**",
        parse_mode="Markdown",
        reply_markup=MENU_CONNECTED
    )


async def ls_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sid = await require_sheet(update, context)
    if not sid:
        return

    ws = get_google_client().open_by_key(sid).sheet1
    ensure_sheet_total(ws)

    total_raw = ws.acell("G1", value_render_option="UNFORMATTED_VALUE").value
    total = total_raw if total_raw is not None else 0

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
        return await update.message.reply_text(
            "⚠️ Chưa có danh sách để xóa.\n\n"
            "👉 Dùng /ls trước để xem danh sách, sau đó dùng `/del <stt>` để xóa.",
            parse_mode="Markdown"
        )

    if not context.args:
        return await update.message.reply_text("⚠️ Cú pháp: `/del <stt>`\nVD: `/del 3`", parse_mode="Markdown")

    try:
        stt = int(context.args[0])
    except ValueError:
        return await update.message.reply_text(
            "⚠️ STT phải là **số**.\n\n"
            "📌 VD: `/del 2` để xóa dòng thứ 2 trong danh sách /ls",
            parse_mode="Markdown"
        )

    sheet_row = ls_map.get(stt)
    if not sheet_row:
        return await update.message.reply_text(
            f"⚠️ Không tìm thấy dòng STT **{stt}**.\n\n"
            "👉 Dùng /ls để xem lại danh sách mới nhất, rồi gõ `/del <stt>`.",
            parse_mode="Markdown"
        )

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
        await update.message.reply_text(
            f"❌ Không xóa được dòng.\n\n"
            f"🔍 Lỗi: `{e}`\n\n"
            "👉 Kiểm tra Bot đã được cấp quyền **Editor** trên Sheet chưa.\n"
            "Dùng /email để lấy email Bot.",
            parse_mode="Markdown"
        )


async def new_book_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text(
            "⚠️ **Thiếu tên sổ!**\n\n"
            "📝 Cú pháp: `/new <tên sổ>`\n\n"
            "📌 VD:\n"
            "• `/new AnSang`\n"
            "• `/new Nhom Ban Than`",
            parse_mode="Markdown"
        )

    book_name = " ".join(context.args)
    await update.message.reply_text(f"⏳ Đang tạo sổ **{book_name}**...", parse_mode="Markdown")

    try:
        gc = get_google_client()
        if not gc:
            return await update.message.reply_text("❌ Lỗi kết nối Google.")

        # Tạo spreadsheet trực tiếp trong folder Drive (nếu có)
        sh = gc.create(book_name, folder_id=DRIVE_FOLDER_ID)
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

        # Lưu vào DB
        await db_upsert_user_sheet(
            update.effective_user.id,
            update.effective_chat.id,
            sh.url,
            sh.id,
            book_name,
        )

        await update.message.reply_text(
            f"✅ **Tạo sổ thành công!**\n"
            f"📂 Tên: **{book_name}**\n"
            f"🔗 [Xem Sheet]({sh.url})\n\n"
            f"👇 Dùng menu bên dưới để thao tác nhanh.",
            parse_mode="Markdown",
            disable_web_page_preview=True,
            reply_markup=MENU_CONNECTED,
        )
    except Exception as e:
        logging.error(f"Lỗi tạo sổ: {e}")
        await update.message.reply_text(
            "⛔ Không thể tạo sổ tự động.\n\n"
            "👉 Hãy tạo thủ công:\n"
            "1️⃣ Tạo Google Sheet mới\n"
            "2️⃣ Share quyền **Editor** cho email Bot (dùng /email để xem)\n"
            "3️⃣ Gửi link Sheet vào đây để kết nối."
        )


async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sid = await require_sheet(update, context)
    if not sid:
        return
    ws = get_google_client().open_by_key(sid).sheet1
    ws.batch_clear(["A2:D1000"])
    await update.message.reply_text("✅ Đã xóa trắng sổ nợ.")


async def delbook_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xóa sổ khỏi Google Drive và DB."""
    uid = update.effective_user.id
    rows = await db_list_user_sheets(uid)
    if not rows:
        return await update.message.reply_text(
            "⚠️ Bạn chưa có sổ nào để xóa.\n\n"
            "👉 Tạo sổ mới: `/new <tên sổ>`\n"
            "Hoặc gửi link Google Sheet vào đây.",
            parse_mode="Markdown"
        )

    context.user_data["books"] = {r["sheet_id"]: r["sheet_title"] for r in rows}
    keyboard = [
        [InlineKeyboardButton(f"🗑 {i+1}. {r['sheet_title']}", callback_data=f"DELBOOK_PICK|{r['sheet_id']}")]
        for i, r in enumerate(rows)
    ]
    await update.message.reply_text(
        "🗑 **Chọn sổ muốn xóa:**\n\n"
        "⚠️ Sổ sẽ bị xóa vĩnh viễn khỏi Google Drive!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def rename_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    rows = await db_list_user_sheets(uid)
    if not rows:
        return await update.message.reply_text(
            "⚠️ Bạn chưa có sổ nào để đổi tên.\n\n"
            "👉 Tạo sổ mới: `/new <tên sổ>`\n"
            "Hoặc gửi link Google Sheet vào đây.",
            parse_mode="Markdown"
        )

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
