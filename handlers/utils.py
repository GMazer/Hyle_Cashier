import logging
from telegram import Update
from telegram.ext import ContextTypes
from db import db_get_user_sheet

def format_vnd(value) -> str:
    """
    Nhận int/float/str (vd: 25000, '25,000', '25.000 đ') -> '25,000 đ'
    """
    if value is None:
        return "0 đ"

    s = str(value).strip()
    digits = "".join(ch for ch in s if ch.isdigit())

    if digits == "":
        return "0 đ"

    n = int(digits)
    return f"{n:,.0f} đ"

async def require_sheet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sid = context.user_data.get("current_sheet_id")
    if sid:
        return sid
    try:
        row = await db_get_user_sheet(update.effective_user.id)
        if row:
            context.user_data["current_sheet_id"] = row["sheet_id"]
            context.user_data["current_sheet_url"] = row["sheet_url"]
            context.user_data["books"] = {row["sheet_id"]: "Sổ đã kết nối"}
            context.user_data["current_book_name"] = "Sổ đã kết nối"
            return row["sheet_id"]
    except Exception as e:
        logging.error(f"require_sheet restore error: {e}")

    await update.message.reply_text(
        "⚠️ Bạn chưa kết nối sổ.\n\n"
        "👉 Hãy gửi link Google Sheet vào đây trước.\n"
        "Hoặc dùng /new để tạo sổ mới."
    )
    return None
