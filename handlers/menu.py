"""
Sticky reply-keyboard menus.

Two layouts depending on whether the user has connected a sheet:
  • MENU_CONNECTED   – full feature access
  • MENU_NEW_USER    – onboarding guidance
"""

from telegram import ReplyKeyboardMarkup, KeyboardButton


# ── Nút bấm ──────────────────────────────────────────────
# Mỗi chuỗi ở đây là *chính xác* text mà Telegram gửi lại
# khi người dùng bấm nút. Message handler sẽ match theo text.

BTN_LS       = "🧾 Xem nợ"
BTN_PAY      = "📲 Thanh toán"
BTN_SO       = "📂 Chọn sổ"
BTN_BANKINFO = "💳 Ngân hàng"
BTN_NEW      = "➕ Tạo sổ"
BTN_HELP     = "📖 Hướng dẫn"
BTN_EMAIL    = "📧 Email Bot"

# Tập hợp tất cả button text để message handler nhận diện
ALL_MENU_BUTTONS = {
    BTN_LS, BTN_PAY, BTN_SO, BTN_BANKINFO,
    BTN_NEW, BTN_HELP, BTN_EMAIL,
}


# ── Layout ────────────────────────────────────────────────

MENU_CONNECTED = ReplyKeyboardMarkup(
    [
        [KeyboardButton(BTN_LS),   KeyboardButton(BTN_PAY)],
        [KeyboardButton(BTN_SO),   KeyboardButton(BTN_BANKINFO)],
        [KeyboardButton(BTN_NEW),  KeyboardButton(BTN_HELP)],
    ],
    resize_keyboard=True,
    is_persistent=True,
)

MENU_NEW_USER = ReplyKeyboardMarkup(
    [
        [KeyboardButton(BTN_NEW),   KeyboardButton(BTN_EMAIL)],
        [KeyboardButton(BTN_HELP)],
    ],
    resize_keyboard=True,
    is_persistent=True,
)


def get_menu(context) -> ReplyKeyboardMarkup:
    """Return the appropriate sticky menu based on user state."""
    if context.user_data.get("current_sheet_id"):
        return MENU_CONNECTED
    return MENU_NEW_USER
