import difflib
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import BANK_CODES
from core.sheets import get_google_client, ensure_sheet_format
from handlers.utils import require_sheet

def normalize_bank_code(raw: str):
    if not raw:
        return None, None
    code = raw.strip().upper()
    if code in BANK_CODES:
        return code, None
    close = difflib.get_close_matches(code, BANK_CODES.keys(), n=1, cutoff=0.6)
    return None, close[0] if close else None


async def bank_menu_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Interactive flow khi bấm nút 💳 Ngân hàng.
    Hiện info nếu đã có, hoặc hướng dẫn nhập nếu chưa có.
    """
    sheet_id = await require_sheet(update, context)
    if not sheet_id:
        return

    book_name = context.user_data.get("current_book_name", "Sổ hiện tại")
    try:
        ws = get_google_client().open_by_key(sheet_id).sheet1
        bank = (ws.acell("I1").value or "").strip()
        stk  = (ws.acell("I2").value or "").strip().lstrip("'")
        name = (ws.acell("I3").value or "").strip()

        if bank and stk:
            # Đã có thông tin → hiển thị + hỏi muốn sửa không
            bank_name = BANK_CODES.get(bank.upper(), bank)
            keyboard = [
                [
                    InlineKeyboardButton("✏️ Chỉnh sửa", callback_data="BANK_EDIT"),
                    InlineKeyboardButton("📲 Tạo QR", callback_data="BANK_PAY"),
                ]
            ]
            await update.message.reply_text(
                f"🏦 **Thông tin ngân hàng — {book_name}**\n\n"
                f"🏛 Ngân hàng: **{bank}** ({bank_name})\n"
                f"💳 STK: `{stk}`\n"
                f"👤 Tên: **{name}**\n\n"
                "👇 Chọn thao tác:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        else:
            # Chưa có → hướng dẫn nhập
            context.user_data["awaiting_bank_input"] = True
            bank_list = ", ".join(f"`{c}`" for c in sorted(BANK_CODES.keys()))
            await update.message.reply_text(
                f"💳 **Sổ \"{book_name}\" chưa có thông tin ngân hàng.**\n\n"
                "📝 Nhập thông tin theo format:\n"
                "`BANK STK TÊN`\n\n"
                "📌 VD: `MB 0862635826 NGUYEN VAN A`\n\n"
                f"🏦 Bank hỗ trợ: {bank_list}",
                parse_mode="Markdown",
            )
    except Exception as e:
        await update.message.reply_text(
            f"❌ Lỗi đọc thông tin ngân hàng.\n"
            f"🔍 `{e}`",
            parse_mode="Markdown"
        )


async def bank_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button callbacks for bank flow."""
    query = update.callback_query
    await query.answer()

    if query.data == "BANK_EDIT":
        context.user_data["awaiting_bank_input"] = True
        bank_list = ", ".join(f"`{c}`" for c in sorted(BANK_CODES.keys()))
        await query.edit_message_text(
            "✏️ **Chỉnh sửa thông tin ngân hàng**\n\n"
            "📝 Nhập thông tin mới theo format:\n"
            "`BANK STK TÊN`\n\n"
            "📌 VD: `MB 0862635826 NGUYEN VAN A`\n\n"
            f"🏦 Bank hỗ trợ: {bank_list}",
            parse_mode="Markdown",
        )
        return

    if query.data == "BANK_PAY":
        await query.edit_message_text("⏳ Đang tạo mã QR...")
        # Gọi pay flow
        sheet_id = await require_sheet(query, context)
        if not sheet_id:
            return
        await _generate_qr(query, context, sheet_id)
        return


async def set_bank_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sheet_id = await require_sheet(update, context)
    if not sheet_id:
        return

    if len(context.args) < 3:
        context.user_data["awaiting_bank_input"] = True
        bank_list = ", ".join(f"`{c}`" for c in sorted(BANK_CODES.keys()))
        return await update.message.reply_text(
            "🏦 **Cài thông tin ngân hàng**\n\n"
            "📝 Nhập theo format:\n"
            "`BANK STK TÊN`\n\n"
            "📌 VD: `MB 0862635826 NGUYEN VAN A`\n\n"
            f"🏦 Bank hỗ trợ: {bank_list}",
            parse_mode="Markdown"
        )

    raw_bank = context.args[0]
    stk = context.args[1].strip()
    name = " ".join(context.args[2:]).strip()

    bank_code, suggestion = normalize_bank_code(raw_bank)
    if not bank_code:
        hint = f"\n\n💡 Có phải bạn muốn dùng `{suggestion}`?" if suggestion else ""
        return await update.message.reply_text(
            f"❌ Bank code `{raw_bank}` không hợp lệ.{hint}\n\n"
            "🏦 **Mã hỗ trợ:** " + ", ".join(f"`{c}`" for c in sorted(BANK_CODES.keys())),
            parse_mode="Markdown"
        )

    if not stk.isdigit() or len(stk) < 6:
        return await update.message.reply_text(
            f"❌ STK `{stk}` không hợp lệ.\n"
            "📌 STK phải là **số** và có **ít nhất 6 chữ số**.",
            parse_mode="Markdown"
        )

    name_up = name.upper()
    try:
        ws = get_google_client().open_by_key(sheet_id).sheet1
        ws.update("H1:H3", [["BANK:"], ["STK:"], ["NAME:"]])
        ws.update_acell("I1", bank_code)
        ws.update_acell("I2", f"'{stk}")
        ws.update_acell("I3", name_up)
    except Exception as e:
        return await update.message.reply_text(
            f"❌ Không ghi được vào Sheet.\n"
            f"🔍 Lỗi: `{e}`",
            parse_mode="Markdown"
        )

    await update.message.reply_text(
        f"✅ **Đã lưu thông tin ngân hàng!**\n\n"
        f"🏛 Bank: **{bank_code}** ({BANK_CODES[bank_code]})\n"
        f"💳 STK: `{stk}`\n"
        f"👤 Tên: **{name_up}**\n\n"
        "📲 Tạo mã QR thanh toán: /pay",
        parse_mode="Markdown"
    )


async def pay_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sheet_id = await require_sheet(update, context)
    if not sheet_id:
        return
    try:
        ws = get_google_client().open_by_key(sheet_id).sheet1
        ensure_sheet_format(ws)
        bank = (ws.acell("I1").value or "").strip()
        stk = (ws.acell("I2").value or "").lstrip("'").strip()
        name = (ws.acell("I3").value or "").strip()

        if not bank or not stk:
            # Chưa có bank → chuyển sang bank_menu_flow
            context.user_data["awaiting_bank_input"] = True
            bank_list = ", ".join(f"`{c}`" for c in sorted(BANK_CODES.keys()))
            return await update.message.reply_text(
                "⚠️ **Chưa có thông tin ngân hàng!**\n\n"
                "📝 Nhập thông tin trước:\n"
                "`BANK STK TÊN`\n\n"
                "📌 VD: `MB 0862635826 NGUYEN VAN A`\n\n"
                f"🏦 Bank hỗ trợ: {bank_list}",
                parse_mode="Markdown"
            )

        total_str = ws.acell("G1", value_render_option="UNFORMATTED_VALUE").value
        total = int(float(total_str or 0))

        if context.args:
            try:
                total = int(float(context.args[0]) * 1000)
            except ValueError:
                return await update.message.reply_text(
                    "❌ Số tiền không hợp lệ.\n\n"
                    "📌 VD:\n"
                    "• `/pay 50` → 50,000 đ\n"
                    "• `/pay` → dùng tổng nợ trong sổ",
                    parse_mode="Markdown"
                )
        if total <= 0:
            return await update.message.reply_text("🎉 Hết nợ! Không cần trả thêm.")

        qr_url = f"https://img.vietqr.io/image/{bank}-{stk}-compact2.png?amount={total}&addInfo=Tra%20tien"
        await update.message.reply_photo(
            photo=qr_url,
            caption=(
                f"💰 Cần trả: **{total:,.0f} VNĐ**\n"
                f"👤 Cho: **{name}**\n"
                f"🏦 Ngân hàng: **{bank}** ({BANK_CODES.get(bank, bank)})\n"
                f"💳 STK: `{stk}`"
            ),
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ Lỗi tạo mã QR.\n"
            f"🔍 `{e}`",
            parse_mode="Markdown"
        )


async def bank_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Alias — redirect to interactive bank_menu_flow."""
    return await bank_menu_flow(update, context)


async def _generate_qr(query, context, sheet_id):
    """Generate QR from inline callback."""
    try:
        ws = get_google_client().open_by_key(sheet_id).sheet1
        bank = (ws.acell("I1").value or "").strip()
        stk = (ws.acell("I2").value or "").lstrip("'").strip()
        name = (ws.acell("I3").value or "").strip()
        total_str = ws.acell("G1", value_render_option="UNFORMATTED_VALUE").value
        total = int(float(total_str or 0))

        if total <= 0:
            return await query.message.reply_text("🎉 Hết nợ!")

        qr_url = f"https://img.vietqr.io/image/{bank}-{stk}-compact2.png?amount={total}&addInfo=Tra%20tien"
        await query.message.reply_photo(
            photo=qr_url,
            caption=(
                f"💰 Cần trả: **{total:,.0f} VNĐ**\n"
                f"👤 Cho: **{name}**\n"
                f"🏦 **{bank}** ({BANK_CODES.get(bank, bank)})\n"
                f"💳 STK: `{stk}`"
            ),
            parse_mode="Markdown"
        )
    except Exception as e:
        await query.message.reply_text(
            f"❌ Lỗi tạo QR: `{e}`",
            parse_mode="Markdown"
        )
