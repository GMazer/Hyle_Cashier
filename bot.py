import logging
import os
import json
import gspread
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, MenuButtonCommands
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from oauth2client.service_account import ServiceAccountCredentials

# --- CẤU HÌNH ---
TOKEN = '8374820897:AAFN5p3mmpu-fcq4OBay7lD4sUV2lVHlEHo'
BOT_EMAIL = "bot-chi-tieu@bot-chi-tieu-485902.iam.gserviceaccount.com"
ADMIN_ID = 1147660391

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- 0. HÀM KẾT NỐI GOOGLE ---
def get_google_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    json_creds = os.environ.get("GOOGLE_CREDENTIALS")
    try:
        if json_creds:
            creds_dict = json.loads(json_creds.strip())
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        elif os.path.exists("cred.json"):
            creds = ServiceAccountCredentials.from_json_keyfile_name("cred.json", scope)
        else: return None
        return gspread.authorize(creds)
    except Exception as e:
        logging.error(f"Lỗi Auth: {e}")
        return None

# --- ÉP CẬP NHẬT MENU LỆNH ---
from telegram import BotCommand, MenuButtonCommands, BotCommandScopeDefault
async def setup_commands(application):
    commands = [
        BotCommand("start", "Bắt đầu / Hướng dẫn kết nối"),
        BotCommand("help", "Xem cách ghi nợ & lệnh tắt"),
        BotCommand("ls", "Xem 10 khoản chi gần nhất"),
        BotCommand("so", "Menu chọn/đổi số nợ"),
        BotCommand("pay", "Tạo mã QR thanh toán"),
        BotCommand("setbank", "Cài ngân hàng (VD: /setbank MB 123 TÊN)"),
        BotCommand("email", "Lấy Email Bot để cấp quyền"),
        BotCommand("new", "Tạo sổ mới"),
        BotCommand("done", "Chốt sổ (Xóa dữ liệu cũ)"),
    ]

    try:
        await application.bot.set_my_commands(commands, scope=BotCommandScopeDefault())
        await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        print("✅ Đã cập nhật Menu lệnh")
    except Exception as e:
        print("❌ setup_commands error:", e)
# --- 1. LỆNH /START (BẢN ĐÃ FIX LẶP & MENU) ---
from telegram import BotCommand, MenuButtonCommands, BotCommandScopeChat

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    # Thu thập ID người dùng
    if 'all_users' not in context.bot_data:
        context.bot_data['all_users'] = set()
    context.bot_data['all_users'].add(update.effective_chat.id)

    user_name = update.effective_user.full_name
    books = context.user_data.get('books', {})
    current_book = context.user_data.get('current_book_name', 'Chưa chọn')

    if books:
        msg = (
            f"👋 **Xin chào {user_name}!**\n\n"
            f"📂 Sổ hiện tại: **{current_book}**\n\n"
            "💵 **Ghi nợ nhanh:**\n"
            "   `Banh mi 20` (Hôm nay)\n"
            "   `30/1 Pho 40` (Ngày cũ)\n\n"
            "⚙️ **Lệnh tắt:** /ls, /so, /pay, /help"
        )
    else:
        msg = (
            f"👋 **Chào mừng {user_name} đến với Bot Ghi Nợ Ăn Sáng!**\n\n"
            f"1️⃣ Share quyền Editor cho: `{BOT_EMAIL}`\n"
            f"2️⃣ Gửi Link Sheet vào đây để kết nối."
        )

    chat_id = update.effective_chat.id

    # --- Set commands cho đúng chat này (đảm bảo Menu hiện) ---
    commands = [
        BotCommand("start", "Bắt đầu / Hướng dẫn kết nối"),
        BotCommand("help", "Xem cách ghi nợ & lệnh tắt"),
        BotCommand("ls", "Xem 10 khoản chi gần nhất"),
        BotCommand("so", "Menu chọn/đổi số nợ"),
        BotCommand("pay", "Tạo mã QR thanh toán"),
        BotCommand("setbank", "Cài ngân hàng"),
        BotCommand("email", "Lấy Email Bot để cấp quyền"),
        BotCommand("new", "Tạo sổ mới"),
        BotCommand("done", "Chốt sổ"),
    ]

    await context.bot.set_my_commands(
        commands,
        scope=BotCommandScopeChat(chat_id)
    )

    # --- Bật nút Menu ---
    await context.bot.set_chat_menu_button(
        chat_id=chat_id,
        menu_button=MenuButtonCommands()
    )

    # --- Gửi đúng nội dung chào mừng ---
    await update.message.reply_text(msg, parse_mode="Markdown")

# --- 2. CÁC LỆNH CƠ BẢN ---
async def email_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"📧 Email Bot:\n`{BOT_EMAIL}`", parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📚 **HƯỚNG DẪN**\n\n"
        "✏️ **Ghi nợ:** `MonAn Tien` (VD: `Xoi 15`)\n"
        "🏦 **QR:** `/setbank MB 123 TEN` -> `/pay` để trả nợ.\n"
        "🛠 **Khác:** `/ls` (Lịch sử), `/so` (Đổi sổ), `/done` (Xóa nợ)."
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

# --- 3. QUẢN LÝ NGÂN HÀNG & QR ---
async def set_bank_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sheet_id = context.user_data.get('current_sheet_id')
    if not sheet_id or len(context.args) < 3:
        await update.message.reply_text("⚠️ Gõ: `/setbank Bank STK Ten` (VD: `/setbank MB 09123 TEN`)", parse_mode='Markdown')
        return
    bank, stk, name = context.args[0].upper(), context.args[1], " ".join(context.args[2:]).upper()
    try:
        ws = get_google_client().open_by_key(sheet_id).sheet1
        ws.update(range_name='H1:I3', values=[["BANK:", bank], ["STK:", f"'{stk}"], ["NAME:", name]])
        await update.message.reply_text(f"✅ Đã lưu STK: {stk} ({bank})")
    except Exception as e: await update.message.reply_text(f"❌ Lỗi: {e}")

async def pay_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sheet_id = context.user_data.get('current_sheet_id')
    if not sheet_id: return
    try:
        ws = get_google_client().open_by_key(sheet_id).sheet1
        bank = ws.acell('I1').value
        
        # ĐỌC VÀ XỬ LÝ STK: Nếu có dấu nháy đơn ở đầu thì xóa đi
        stk_raw = ws.acell('I2').value or ""
        stk = stk_raw.lstrip("'") 
        
        name = ws.acell('I3').value
        
        total_val = (ws.acell('G1').value or "0").replace(',','').replace('.','')
        total = int(total_val)
        
        if context.args: total = int(context.args[0]) * 1000
        if total <= 0: return await update.message.reply_text("🎉 Hết nợ!")
        
        # API VietQR với STK đã được làm sạch
        qr_url = f"https://img.vietqr.io/image/{bank}-{stk}-compact2.png?amount={total}&addInfo=Tra%20tien%20an%20sang"
        
        await update.message.reply_photo(
            photo=qr_url, 
            caption=f"💰 Cần trả: {total:,.0f} VNĐ cho {name}\n💳 STK: `{stk}`"
        )
    except Exception as e: 
        await update.message.reply_text(f"⚠️ Sổ chưa cài STK hoặc lỗi: {e}")

        # --- 4. LỆNH /NEW: TỰ ĐỘNG TẠO FILE GOOGLE SHEET MỚI ---
async def new_book_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("⚠️ Hãy nhập tên sổ. VD: `/new AnSang`", parse_mode='Markdown')
        return
    
    book_name = " ".join(args)
    await update.message.reply_text(f"⏳ Đang tạo sổ **{book_name}** trên Google Drive...")

    try:
        gc = get_google_client()
        if not gc:
            await update.message.reply_text("❌ Lỗi kết nối Google.")
            return

        # Tạo file Sheet mới
        sh = gc.create(book_name)
        # Chia sẻ quyền truy cập (cho phép Bot viết vào file vừa tạo)
        sh.share(None, perm_type='anyone', role='writer')
        
        ws = sh.sheet1
        # Cấu hình tiêu đề cột
        ws.update(range_name='A1:D1', values=[["Ngày", "Món", "Tiền", "Ghi chú"]])
        ws.update_acell('F1', "TỔNG NỢ:")
        ws.update_acell('G1', "=SUM(C:C)")
        
        # Định dạng in đậm cho tổng tiền
        ws.format("G1", {"textFormat": {"bold": True, "foregroundColor": {"red": 1.0}}})

        # Lưu vào bộ nhớ của Bot
        if 'books' not in context.user_data: context.user_data['books'] = {}
        context.user_data['books'][sh.id] = book_name
        context.user_data['current_sheet_id'] = sh.id
        context.user_data['current_book_name'] = book_name

        await update.message.reply_text(
            f"✅ **ĐÃ TẠO SỔ THÀNH CÔNG!**\n\n"
            f"📂 Tên sổ: **{book_name}**\n"
            f"🔗 [Bấm vào đây để xem Sheet]({sh.url})", 
            parse_mode='Markdown', 
            disable_web_page_preview=True
        )
    except Exception as e:
        logging.error(f"Lỗi tạo sổ: {e}")
        await update.message.reply_text("⛔ Bot bị Google chặn tạo file tự động.\n👉 Hãy tạo thủ công rồi gửi Link vào đây nhé.")

# --- 4. XỬ LÝ TIN NHẮN & BROADCAST ---
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    msg = update.message.text.replace('/broadcast', '').strip()
    users = context.bot_data.get('all_users', set())
    for uid in users:
        try: await context.bot.send_message(chat_id=uid, text=f"📢 **THÔNG BÁO:**\n\n{msg}", parse_mode='Markdown')
        except: pass
    await update.message.reply_text("✅ Đã gửi xong.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'all_users' not in context.bot_data: context.bot_data['all_users'] = set()
    context.bot_data['all_users'].add(update.effective_chat.id)
    text = update.message.text.strip()
    
    # Nhận Link Sheet
    if "docs.google.com" in text:
        try:
            sh = get_google_client().open_by_url(text)
            context.user_data['books'] = {sh.id: sh.title}
            context.user_data['current_sheet_id'], context.user_data['current_book_name'] = sh.id, sh.title
            await update.message.reply_text(f"✅ Đã kết nối sổ: {sh.title}")
        except: await update.message.reply_text("❌ Lỗi quyền truy cập!")
        return

    # Ghi nợ
    sid = context.user_data.get('current_sheet_id')
    if not sid: return
    try:
        ws = get_google_client().open_by_key(sid).sheet1
        parts = text.split()
        if len(parts) < 2: return
        amt = float(parts[-1]) * 1000
        item = " ".join(parts[:-1])
        ws.append_row([datetime.now().strftime("%d/%m/%Y"), item, amt])
        await update.message.reply_text(f"✅ Ghi: {item} ({amt:,.0f})\n💰 Tổng: {ws.acell('G1').value}")
    except: pass

# --- CÁC HÀM CÒN LẠI (GIỮ NGUYÊN) ---
async def list_books_command(update, context):
    books = context.user_data.get('books', {})
    keyboard = [[InlineKeyboardButton(name, callback_data=f"SELECT|{id}")] for id, name in books.items()]
    await update.message.reply_text("📂 Chọn sổ:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_callback(update, context):
    query = update.callback_query
    await query.answer()
    _, bid = query.data.split("|")
    context.user_data['current_sheet_id'] = bid
    await query.edit_message_text(f"✅ Đã chọn sổ mới.")

async def ls_command(update, context):
    sid = context.user_data.get('current_sheet_id')
    ws = get_google_client().open_by_key(sid).sheet1
    last_5 = ws.get_all_values()[-5:]
    msg = "\n".join([f"{r[0]} | {r[1]}: {r[2]}" for r in last_5])
    await update.message.reply_text(f"🧾 5 dòng gần nhất:\n{msg}\n💰 TỔNG: {ws.acell('G1').value}")

async def done_command(update, context):
    ws = get_google_client().open_by_key(context.user_data.get('current_sheet_id')).sheet1
    ws.batch_clear(['A2:D1000'])
    await update.message.reply_text("✅ Đã xóa trắng sổ nợ.")

# --- MAIN BLOCK ---
if __name__ == '__main__':
    # 1. Khởi tạo Application
    # Mình bỏ post_init để tránh xung đột gây lặp tin nhắn
    application = ApplicationBuilder().token(TOKEN).post_init(setup_commands).build()
    
    # 2. Đăng ký TẤT CẢ các lệnh (Viết ở đây là chắc ăn nhất)
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('ls', ls_command))
    application.add_handler(CommandHandler('so', list_books_command))
    application.add_handler(CommandHandler('new', new_book_command))
    application.add_handler(CommandHandler('email', email_command))
    application.add_handler(CommandHandler('done', done_command))
    application.add_handler(CommandHandler('setbank', set_bank_command))
    application.add_handler(CommandHandler('pay', pay_command))
    application.add_handler(CommandHandler('broadcast', broadcast_command))
    
    # Đăng ký xử lý nút bấm & tin nhắn text
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # 3. Chạy Bot
    WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL") 
    PORT = int(os.environ.get("PORT", "8443"))

    if WEBHOOK_URL:
        # Khi chạy Webhook, ta gọi setup_commands thủ công một lần để ép hiện Menu
        import asyncio

        
        application.run_webhook(listen="0.0.0.0", port=PORT, url_path=TOKEN, webhook_url=f"{WEBHOOK_URL}/{TOKEN}")
    else:
        application.run_polling()