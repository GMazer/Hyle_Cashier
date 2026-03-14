import re
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from core.database import db_touch_user, db_upsert_user_sheet
from core.sheets import get_google_client, ensure_sheet_total, format_vnd
from handlers.utils import require_sheet
from handlers.books import handle_rename_input
from handlers.menu import (
    ALL_MENU_BUTTONS, BTN_LS, BTN_PAY, BTN_SO,
    BTN_BANKINFO, BTN_NEW, BTN_HELP, BTN_REPORT,
    get_menu, MENU_CONNECTED,
)


def _parse_entry_line(line: str, today: datetime):
    remaining = line.strip()
    if not remaining:
        return None

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

    money_match = re.search(r"(\d+(?:\.\d+)?)\s*$", remaining)
    if not money_match:
        all_nums = list(re.finditer(r"\d+(?:\.\d+)?", remaining))
        if not all_nums:
            return None
        money_match = all_nums[-1]

    amount = int(float(money_match.group()) * 1000)
    before_money = remaining[:money_match.start()].strip()
    after_money = remaining[money_match.end():].strip()

    item = before_money if before_money else "Khác"
    note = after_money

    return [date_str, item, amount, note]

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await db_touch_user(update.effective_user.id, update.effective_chat.id)
    text = update.message.text.strip()

    # ── Xử lý sticky menu buttons ──
    if text in ALL_MENU_BUTTONS:
        return await _handle_menu_button(update, context, text)

    # ── Awaiting input flows ──

    # Đang chờ nhập tên sổ mới
    if context.user_data.get("awaiting_new_book"):
        context.user_data.pop("awaiting_new_book", None)
        # Inject text as args và gọi new_book_command
        context.args = text.split()
        from handlers.books import new_book_command
        return await new_book_command(update, context)

    # Đang chờ nhập thông tin ngân hàng
    if context.user_data.get("awaiting_bank_input"):
        context.user_data.pop("awaiting_bank_input", None)
        context.args = text.split()
        from handlers.bank import set_bank_command
        return await set_bank_command(update, context)

    # Đang chờ nhập báo lỗi / góp ý
    if context.user_data.get("awaiting_issue_report"):
        context.user_data.pop("awaiting_issue_report", None)
        from handlers.admin import submit_issue_report
        return await submit_issue_report(update, context)

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
            await update.message.reply_text(
                f"✅ Đã kết nối sổ: **{sheet_title}**\n\n"
                "👇 Dùng menu bên dưới để thao tác.",
                parse_mode="Markdown",
                reply_markup=MENU_CONNECTED
            )
        except Exception as e:
            logging.error(f"Sheet error: {e}")
            await update.message.reply_text(
                f"❌ Không kết nối được Sheet.\n\n"
                f"🔍 Lỗi: `{e}`",
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

        today = datetime.now()
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return

        entries = []
        invalid_lines = []
        for idx, line in enumerate(lines, 1):
            parsed = _parse_entry_line(line, today)
            if parsed is None:
                invalid_lines.append(idx)
                continue
            entries.append(parsed)

        if not entries:
            return await update.message.reply_text(
                "❌ Không nhận được khoản hợp lệ nào.\n\n"
                "Ví dụ nhập nhiều dòng:\n"
                "`cafe 25`\n"
                "`banh mi 20`\n"
                "`gui xe 5`",
                parse_mode="Markdown"
            )

        start_row = len(ws.col_values(1)) + 1
        end_row = start_row + len(entries) - 1
        ws.update(f"A{start_row}:D{end_row}", entries)

        total_raw = ws.acell("G1", value_render_option="UNFORMATTED_VALUE").value
        total = total_raw if total_raw is not None else 0
        total_added = sum(entry[2] for entry in entries)

        preview_lines = [
            f"• {item} ({format_vnd(amount)})"
            for _, item, amount, _ in entries[:5]
        ]
        if len(entries) > 5:
            preview_lines.append(f"• ... và thêm {len(entries) - 5} khoản nữa")

        message = (
            f"✅ Đã ghi **{len(entries)} khoản**\n"
            f"📋 " + "\n".join(preview_lines) + "\n"
            f"💸 Cộng thêm: {format_vnd(total_added)}\n"
            f"💰 Tổng: {format_vnd(total)}"
        )

        if invalid_lines:
            bad = ", ".join(str(i) for i in invalid_lines[:10])
            message += f"\n⚠️ Bỏ qua dòng lỗi: {bad}"
            if len(invalid_lines) > 10:
                message += "..."

        await update.message.reply_text(message, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Ghi nợ lỗi: {e}")
        await update.message.reply_text(
            f"❌ Không ghi được vào sổ.\n\n"
            f"🔍 Lỗi: `{e}`\n\n"
            "👉 Thử dùng /so để chọn lại sổ.",
            parse_mode="Markdown"
        )


async def _handle_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Dispatch sticky-menu button presses to interactive flows."""

    # ── 🧾 Xem nợ → trực tiếp hiển thị ──
    if text == BTN_LS:
        from handlers.books import ls_command
        return await ls_command(update, context)

    # ── 📲 Thanh toán → trực tiếp tạo QR ──
    if text == BTN_PAY:
        from handlers.bank import pay_command
        return await pay_command(update, context)

    # ── 📂 Chọn sổ → hiện danh sách ──
    if text == BTN_SO:
        from handlers.books import list_books_command
        return await list_books_command(update, context)

    # ── 💳 Ngân hàng → hiển thị info + gợi ý chỉnh sửa ──
    if text == BTN_BANKINFO:
        from handlers.bank import bank_menu_flow
        return await bank_menu_flow(update, context)

    # ── ➕ Tạo sổ → hỏi tên, chờ input ──
    if text == BTN_NEW:
        context.user_data["awaiting_new_book"] = True
        menu = get_menu(context)
        return await update.message.reply_text(
            "➕ **Tạo sổ mới**\n\n"
            "📝 Nhập tên sổ muốn tạo:\n\n"
            "📌 VD: `AnSang` hoặc `Nhom Ban Than`",
            parse_mode="Markdown",
            reply_markup=menu
        )

    # ── 📖 Hướng dẫn ──
    if text == BTN_HELP:
        from handlers.start_help import help_command
        return await help_command(update, context)

    # ── 🚨 Báo lỗi ──
    if text == BTN_REPORT:
        from handlers.admin import report_issue_command
        return await report_issue_command(update, context)
