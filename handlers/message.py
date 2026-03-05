import re
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from db import db_touch_user, db_upsert_user_sheet
from sheets import get_google_client, ensure_sheet_total, format_vnd
from handlers.utils import require_sheet
from handlers.books import handle_rename_input

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await db_touch_user(update.effective_user.id, update.effective_chat.id)
    text = update.message.text.strip()

    # Ưu tiên xử lý rename nếu đang chờ nhập tên mới
    if await handle_rename_input(update, context):
        return

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
            await update.message.reply_text(
                f"❌ Không kết nối được Sheet.\n\n"
                f"🔍 Lỗi: `{e}`\n\n"
                "👉 Kiểm tra:\n"
                "• Link Sheet có đúng không?\n"
                "• Bot đã được share quyền **Editor** chưa?\n"
                "• Dùng /email để lấy email Bot.",
                parse_mode="Markdown"
            )
        return

    # Ghi nợ
    sid = await require_sheet(update, context)
    if not sid:
        return

    try:
        ws = get_google_client().open_by_key(sid).sheet1
        ensure_sheet_total(ws)

        # --- Parse input ---
        # Format: [ngày] <tên món> <số tiền> [ghi chú]
        # VD: "26/2 xúc xích 10"   → ngày=26/02/2026, item=xúc xích, amount=10k
        #     "Banh mi 20"          → ngày=hôm nay, item=Banh mi, amount=20k
        #     "Pho 40 ngon lắm"     → ngày=hôm nay, item=Pho, amount=40k, note=ngon lắm

        remaining = text
        today = datetime.now()

        # 1) Tách ngày ở đầu (nếu có): d/m hoặc d/m/y
        date_match = re.match(r"^(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\s+", remaining)
        if date_match:
            day = int(date_match.group(1))
            month = int(date_match.group(2))
            year_str = date_match.group(3)
            if year_str:
                year = int(year_str)
                if year < 100:
                    year += 2000
            else:
                year = today.year
            try:
                date_str = f"{day:02d}/{month:02d}/{year}"
            except Exception:
                date_str = today.strftime("%d/%m/%Y")
            remaining = remaining[date_match.end():]
        else:
            date_str = today.strftime("%d/%m/%Y")

        # 2) Tách số tiền (số cuối cùng trong chuỗi còn lại)
        money_match = re.search(r"(\d+(?:\.\d+)?)\s*$", remaining)
        if not money_match:
            # Thử tìm số cuối cùng bất kỳ đâu
            all_nums = list(re.finditer(r"\d+(?:\.\d+)?", remaining))
            if not all_nums:
                return
            money_match = all_nums[-1]

        amount = float(money_match.group()) * 1000
        amount = int(amount)  # Ghi số nguyên vào sheet, tránh float issue

        # 3) Phần trước số tiền = tên món, phần sau = ghi chú
        before_money = remaining[:money_match.start()].strip()
        after_money = remaining[money_match.end():].strip()

        item = before_money if before_money else "Khác"
        note = after_money

        next_row = len(ws.col_values(1)) + 1
        ws.update(f"A{next_row}:D{next_row}", [[
            date_str,
            item,
            amount,
            note,
        ]])

       # sau khi ws.update(...) xong
        total_raw = ws.acell("G1", value_render_option="UNFORMATTED_VALUE").value
        total = total_raw if total_raw is not None else 0

        await update.message.reply_text(
            f"✅ Ghi: {item} ({format_vnd(amount)})\n"
            f"� Ngày: {date_str}\n"
            f"�📝 Ghi chú: {note if note else '—'}\n"
            f"💰 Tổng: {format_vnd(total)}"
        )
    except Exception as e:
        logging.error(f"Ghi nợ lỗi: {e}")
        await update.message.reply_text(
            f"❌ Không ghi được vào sổ.\n\n"
            f"🔍 Lỗi: `{e}`\n\n"
            "👉 Thử:\n"
            "• Dùng /so để chọn lại sổ\n"
            "• Hoặc gửi lại link Sheet\n"
            "• Kiểm tra Bot có quyền Editor: /email",
            parse_mode="Markdown"
        )
