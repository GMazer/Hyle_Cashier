import difflib
from telegram import Update
from telegram.ext import ContextTypes
from config import BANK_CODES
from sheets import get_google_client, ensure_sheet_format
from handlers.utils import require_sheet

def normalize_bank_code(raw: str):
    if not raw:
        return None, None
    code = raw.strip().upper()
    if code in BANK_CODES:
        return code, None
    close = difflib.get_close_matches(code, BANK_CODES.keys(), n=1, cutoff=0.6)
    return None, close[0] if close else None


async def set_bank_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sheet_id = await require_sheet(update, context)
    if not sheet_id:
        return

    if len(context.args) < 3:
        return await update.message.reply_text(
            "⚠️ **Thiếu thông tin!**\n\n"
            "📝 Cú pháp: `/setbank <BANK> <STK> <TÊN>`\n\n"
            "📌 **Ví dụ:**\n"
            "`/setbank MB 0862635826 NGUYEN VAN NANG`\n\n"
            "🏦 **Bank code hỗ trợ:**\n`" + "`, `".join(sorted(BANK_CODES.keys())) + "`",
            parse_mode="Markdown"
        )

    raw_bank = context.args[0]
    stk = context.args[1].strip()
    name = " ".join(context.args[2:]).strip()

    bank_code, suggestion = normalize_bank_code(raw_bank)
    if not bank_code:
        hint = f"\n\n� Có phải bạn muốn dùng `{suggestion}`? Gõ lại:\n`/setbank {suggestion} {stk} {name}`" if suggestion else ""
        return await update.message.reply_text(
            f"❌ Bank code `{raw_bank}` không hợp lệ.\n\n"
            "🏦 **Mã ngân hàng hỗ trợ:**\n`" + "`, `".join(sorted(BANK_CODES.keys())) + "`" + hint,
            parse_mode="Markdown"
        )

    if not stk.isdigit() or len(stk) < 6:
        return await update.message.reply_text(
            f"❌ Số tài khoản `{stk}` không hợp lệ.\n\n"
            "📌 STK phải là **số** và có **ít nhất 6 chữ số**.\n"
            f"👉 VD: `/setbank {raw_bank} 0862635826 {name}`",
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
            f"❌ Không ghi được vào Sheet.\n\n"
            f"🔍 Lỗi: `{e}`\n\n"
            "👉 Kiểm tra lại:\n"
            "• Bot đã được cấp quyền **Editor** trên Sheet chưa?\n"
            "• Dùng /email để lấy email Bot và share quyền.",
            parse_mode="Markdown"
        )

    await update.message.reply_text(
        f"✅ Đã lưu:\n- Bank: **{bank_code}** ({BANK_CODES[bank_code]})\n"
        f"- STK: `{stk}`\n- Tên: **{name_up}**",
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
            book_name = context.user_data.get("current_book_name", "sổ hiện tại")
            return await update.message.reply_text(
                f"⚠️ Sổ **{book_name}** chưa cài thông tin ngân hàng.\n\n"
                "👉 Hãy cài đặt trước bằng lệnh:\n"
                "`/setbank <BANK> <STK> <TÊN>`\n\n"
                "📌 VD: `/setbank MB 0862635826 NGUYEN VAN NANG`\n\n"
                "Sau đó gõ lại /pay để tạo mã QR.",
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
                    "📌 Nhập số nghìn đồng:\n"
                    "• `/pay 50` → 50,000 đ\n"
                    "• `/pay 50.5` → 50,500 đ\n"
                    "• `/pay` (không số) → dùng tổng nợ trong sổ",
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
            f"❌ Lỗi tạo mã QR thanh toán.\n\n"
            f"🔍 Chi tiết: `{e}`\n\n"
            "👉 Thử:\n"
            "• Kiểm tra thông tin bank: /bankinfo\n"
            "• Cài lại: `/setbank <BANK> <STK> <TÊN>`",
            parse_mode="Markdown"
        )


async def bank_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sheet_id = await require_sheet(update, context)
    if not sheet_id:
        return

    book_name = context.user_data.get("current_book_name", "Sổ hiện tại")
    try:
        ws = get_google_client().open_by_key(sheet_id).sheet1
        bank = (ws.acell("I1").value or "").strip()
        stk  = (ws.acell("I2").value or "").strip().lstrip("'")
        name = (ws.acell("I3").value or "").strip()

        if not bank and not stk and not name:
            return await update.message.reply_text(
                f"⚠️ Sổ **{book_name}** chưa cài thông tin ngân hàng.\n\n"
                "👉 Cài đặt ngay:\n"
                "`/setbank <BANK> <STK> <TÊN>`\n\n"
                "📌 VD: `/setbank MB 0862635826 NGUYEN VAN NANG`",
                parse_mode="Markdown"
            )

        bank_name = BANK_CODES.get(bank.upper(), bank)
        await update.message.reply_text(
            f"🏦 **Thông tin thanh toán — {book_name}**\n\n"
            f"🏛 Ngân hàng: **{bank}** ({bank_name})\n"
            f"💳 STK: `{stk}`\n"
            f"👤 Tên: **{name}**\n\n"
            "📲 Tạo mã QR: /pay\n"
            "✏️ Thay đổi: `/setbank <BANK> <STK> <TÊN>`",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ Lỗi đọc thông tin ngân hàng.\n\n"
            f"🔍 Chi tiết: `{e}`\n\n"
            "👉 Thử dùng /so để chọn lại sổ, hoặc gửi lại link Sheet.",
            parse_mode="Markdown"
        )
