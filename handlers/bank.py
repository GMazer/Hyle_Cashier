import difflib
from telegram import Update
from telegram.ext import ContextTypes
from config import BANK_CODES
from sheets import get_google_client, ensure_sheet_format

def normalize_bank_code(raw: str):
    if not raw:
        return None, None
    code = raw.strip().upper()
    if code in BANK_CODES:
        return code, None
    close = difflib.get_close_matches(code, BANK_CODES.keys(), n=1, cutoff=0.6)
    return None, close[0] if close else None


async def set_bank_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sheet_id = context.user_data.get("current_sheet_id")
    if not sheet_id:
        return await update.message.reply_text(
            "⚠️ Bạn chưa kết nối Sheet.\n👉 Gửi link Google Sheet trước, rồi gõ lại /setbank."
        )

    if len(context.args) < 3:
        return await update.message.reply_text(
            "⚠️ Cú pháp: `/setbank <BANK_CODE> <STK> <TEN>`\n\n"
            "Ví dụ: `/setbank MB 0862635826 NGUYEN VAN NANG`\n\n"
            "Bank code hỗ trợ: " + ", ".join(sorted(BANK_CODES.keys())),
            parse_mode="Markdown"
        )

    raw_bank = context.args[0]
    stk = context.args[1].strip()
    name = " ".join(context.args[2:]).strip()

    bank_code, suggestion = normalize_bank_code(raw_bank)
    if not bank_code:
        hint = f"\n👉 Bạn có muốn dùng `{suggestion}` không?" if suggestion else ""
        return await update.message.reply_text(
            "⚠️ Bank code không hợp lệ.\nMã hỗ trợ: " + ", ".join(sorted(BANK_CODES.keys())) + hint,
            parse_mode="Markdown"
        )

    if not stk.isdigit() or len(stk) < 6:
        return await update.message.reply_text("⚠️ STK không hợp lệ. Phải là số và >= 6 ký tự.")

    name_up = name.upper()
    try:
        ws = get_google_client().open_by_key(sheet_id).sheet1
        ws.update("H1:H3", [["BANK:"], ["STK:"], ["NAME:"]])
        ws.update_acell("I1", bank_code)
        ws.update_acell("I2", f"'{stk}")
        ws.update_acell("I3", name_up)
    except Exception as e:
        return await update.message.reply_text(f"⚠️ Không ghi được vào Sheet: {e}")

    await update.message.reply_text(
        f"✅ Đã lưu:\n- Bank: **{bank_code}** ({BANK_CODES[bank_code]})\n"
        f"- STK: `{stk}`\n- Tên: **{name_up}**",
        parse_mode="Markdown"
    )


async def pay_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sheet_id = context.user_data.get("current_sheet_id")
    if not sheet_id:
        return await update.message.reply_text("⚠️ Chưa kết nối sổ.")
    try:
        ws = get_google_client().open_by_key(sheet_id).sheet1
        ensure_sheet_format(ws)
        bank = ws.acell("I1").value
        stk = (ws.acell("I2").value or "").lstrip("'")
        name = ws.acell("I3").value

        total_str = ws.acell("G1", value_render_option="UNFORMATTED_VALUE").value
        total = int(float(total_str or 0))

        if context.args:
            total = int(context.args[0]) * 1000
        if total <= 0:
            return await update.message.reply_text("🎉 Hết nợ!")

        qr_url = f"https://img.vietqr.io/image/{bank}-{stk}-compact2.png?amount={total}&addInfo=Tra%20tien"
        await update.message.reply_photo(
            photo=qr_url,
            caption=f"💰 Cần trả: {total:,.0f} VNĐ cho {name}\n💳 STK: `{stk}`",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ Sổ chưa cài STK hoặc lỗi: {e}")


async def bank_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sheet_id = context.user_data.get("current_sheet_id")
    if not sheet_id:
        return await update.message.reply_text("⚠️ Chưa kết nối sổ. Dùng /so để chọn sổ.")

    book_name = context.user_data.get("current_book_name", "Sổ hiện tại")
    try:
        ws = get_google_client().open_by_key(sheet_id).sheet1
        bank = (ws.acell("I1").value or "").strip()
        stk  = (ws.acell("I2").value or "").strip().lstrip("'")
        name = (ws.acell("I3").value or "").strip()

        if not bank and not stk and not name:
            return await update.message.reply_text(
                f"⚠️ Sổ **{book_name}** chưa cài thông tin ngân hàng.\n"
                "👉 Dùng `/setbank <BANK> <STK> <TÊN>` để cài.",
                parse_mode="Markdown"
            )

        bank_name = BANK_CODES.get(bank.upper(), bank)
        await update.message.reply_text(
            f"🏦 **Thông tin thanh toán - {book_name}**\n\n"
            f"🏛 Ngân hàng: **{bank}** ({bank_name})\n"
            f"💳 STK: `{stk}`\n"
            f"👤 Tên: **{name}**",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ Lỗi đọc thông tin ngân hàng: {e}")
