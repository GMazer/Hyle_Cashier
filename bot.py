import logging
import os
import json
import gspread
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from oauth2client.service_account import ServiceAccountCredentials

# --- CẤU HÌNH ---
TOKEN = '8374820897:AAGLUxuxF5XqlZgHA4O6X8rmMWsJWo4sGqE'
BOT_EMAIL = "bot-chi-tieu@bot-chi-tieu-485902.iam.gserviceaccount.com"

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- HÀM KẾT NỐI GOOGLE ---
def get_google_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    json_creds = os.environ.get("GOOGLE_CREDENTIALS")
    
    try:
        if json_creds:
            clean_json = json_creds.strip()
            creds_dict = json.loads(clean_json)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        elif os.path.exists("cred.json"):
            creds = ServiceAccountCredentials.from_json_keyfile_name("cred.json", scope)
        else:
            return None
        return gspread.authorize(creds)
    except Exception as e:
        logging.error(f"Lỗi Auth: {e}")
        return None

# --- LỆNH START: HƯỚNG DẪN NGƯỜI MỚI ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.full_name
    
    # Kiểm tra xem đã có sổ nào chưa
    books = context.user_data.get('books', {})
    current_book = context.user_data.get('current_book_name', 'Chưa chọn')

    # Nếu đã có sổ rồi -> Hiện giao diện chính
    if books:
        msg = (
            f"👋 **Xin chào {user_name}!**\n\n"
            f"📂 Sổ hiện tại: **{current_book}**\n\n"
            "💵 **Nhập chi tiêu:**\n"
            "   `Cafe 25` (Hôm nay)\n"
            "   `30/1 Cafe 25` (Ngày cụ thể)\n\n"
            "⚙️ **Menu:**\n"
            "   /ls - Xem lịch sử gần nhất\n"
            "   /so - Đổi sổ khác\n"
            "   /email - Lấy email Bot để Share\n"
            "   /help - Xem hướng dẫn đầy đủ"
        )
        await update.message.reply_text(msg, parse_mode='Markdown')
    else:
        # Nếu chưa có sổ -> Hướng dẫn kết nối (Onboarding)
        msg = (
            f"👋 **Chào mừng {user_name} đến với Bot Quản Lý Tài Chính!**\n\n"
            "Để bắt đầu ghi chép, chúng ta cần kết nối với 1 file Google Sheet. Hãy làm theo 3 bước sau:\n\n"
            "1️⃣ **Tạo Sổ:** Vào Google Drive tạo 1 file Google Sheet mới.\n\n"
            "2️⃣ **Cấp Quyền:** Bấm nút **Share (Chia sẻ)** và dán email này vào (Quyền **Editor**):\n"
            f"`{BOT_EMAIL}`\n"
            "👆 _(Bấm vào dòng trên để copy nhanh)_\n\n"
            "3️⃣ **Kết Nối:** Copy đường Link của file Sheet đó và **Gửi vào đây**."
        )
        await update.message.reply_text(msg, parse_mode='Markdown')

# --- LỆNH EMAIL (MỚI): LẤY EMAIL NHANH ---
async def email_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📧 **Email của Bot (Service Account):**\n\n"
        f"`{BOT_EMAIL}`\n\n"
        "👆 _Bấm vào dòng trên để copy._\n"
        "Hãy Share quyền **Editor** (Người chỉnh sửa) cho email này trong Google Sheet nhé!",
        parse_mode='Markdown'
    )

# --- LỆNH HELP: CHI TIẾT ---
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📚 **HƯỚNG DẪN SỬ DỤNG**\n\n"
        "✏️ **1. Cách ghi tiền:**\n"
        "• `Tên món + Tiền` (Tự lấy ngày hôm nay)\n"
        "   VD: `An sang 30` (Hiểu là 30k)\n"
        "   VD: `Cafe 25.5` (Hiểu là 25,500đ)\n"
        "• `Ngày + Tên món + Tiền` (Ghi bù ngày cũ)\n"
        "   VD: `25/1 Luong ve 10000` (Ngày 25/1)\n\n"
        "📂 **2. Quản lý Sổ:**\n"
        "• **Thêm sổ:** Gửi Link Google Sheet vào đây.\n"
        "• **Đổi sổ:** Gõ `/so` để chọn sổ khác.\n"
        "• **Tạo mới:** Gõ `/new TênSổ` (Thử tự tạo).\n\n"
        "🛠 **3. Tiện ích:**\n"
        "• `/ls` : Xem 10 dòng cuối & Tổng tiền.\n"
        "• `/email` : Lấy email Bot để share.\n"
        "• `done` : Chốt sổ (Xóa dữ liệu cũ, sang tháng mới)."
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

# --- LỆNH NEW ---
async def new_book_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("⚠️ Hãy nhập tên sổ. VD: `/new Quỹ Đen`", parse_mode='Markdown')
        return
    
    book_name = " ".join(args)
    await update.message.reply_text(f"⏳ Đang tạo sổ **{book_name}**...")

    try:
        gc = get_google_client()
        sh = gc.create(book_name)
        sh.share(None, perm_type='anyone', role='writer')
        
        ws = sh.sheet1
        ws.update(values=[["Ngày", "Món", "Tiền", "Ghi chú"]], range_name='A1:D1')
        ws.update_acell('F1', "TỔNG QUỸ:")
        ws.update_acell('G1', "=SUM(C:C)")
        ws.format("G1", {"textFormat": {"bold": True, "foregroundColor": {"red": 1.0}}})

        if 'books' not in context.user_data: context.user_data['books'] = {}
        context.user_data['books'][sh.id] = book_name
        context.user_data['current_sheet_id'] = sh.id
        context.user_data['current_book_name'] = book_name

        await update.message.reply_text(f"✅ Đã tạo: [{book_name}]({sh.url})", parse_mode='Markdown', disable_web_page_preview=True)
    except Exception:
        await update.message.reply_text(
            "⛔ Bot không tự tạo được file (Google chặn).\n"
            "👉 Hãy tạo thủ công rồi gửi Link vào đây nhé.\n"
            "Cần email share? Gõ `/email`"
        )

# --- LỆNH SO (MENU CHỌN SỔ) ---
async def list_books_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    books = context.user_data.get('books', {})
    if not books:
        await update.message.reply_text("⚠️ Bạn chưa có sổ nào. Gửi Link Sheet để thêm nhé.")
        return

    current_id = context.user_data.get('current_sheet_id')
    keyboard = []
    for bid, bname in books.items():
        label = f"✅ {bname}" if bid == current_id else bname
        keyboard.append([InlineKeyboardButton(label, callback_data=f"SELECT|{bid}")])

    await update.message.reply_text("📂 **CHỌN SỔ CHI TIÊU:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# --- BUTTON CALLBACK ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split("|")
    if data[0] == "SELECT":
        selected_id = data[1]
        books = context.user_data.get('books', {})
        book_name = books.get(selected_id, "Không tên")
        context.user_data['current_sheet_id'] = selected_id
        context.user_data['current_book_name'] = book_name
        await query.edit_message_text(f"✅ Đã chuyển sang: **{book_name}**", parse_mode='Markdown')

# --- LỆNH LS ---
async def ls_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sheet_id = context.user_data.get('current_sheet_id')
    if not sheet_id:
        await update.message.reply_text("⚠️ Chưa chọn sổ. Gõ `/so` hoặc gửi Link.")
        return

    try:
        await update.message.reply_text("⏳ Đang tải...")
        gc = get_google_client()
        ws = gc.open_by_key(sheet_id).sheet1
        vals = ws.get_all_values()
        
        if len(vals) < 2:
            await update.message.reply_text("📭 Sổ trống.")
            return

        last_10 = vals[1:][-10:]
        msg = f"🧾 **{context.user_data.get('current_book_name')}**\n" + "-"*20 + "\n"
        for r in last_10:
            d = r[0] if len(r)>0 else ""
            n = r[1] if len(r)>1 else ""
            m = r[2] if len(r)>2 else "0"
            try: m_fmt = "{:,.0f}".format(float(m.replace(',','').replace('.','')))
            except: m_fmt = m
            msg += f"{d} | {n} : **{m_fmt}**\n"
            
        total = ws.acell('G1').value or "0"
        msg += "-"*20 + f"\n💰 **TỔNG: {total} VNĐ**"
        await update.message.reply_text(msg, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"⚠️ Lỗi: {str(e)}")

# --- XỬ LÝ MESSAGE ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    # 1. NHẬN LINK
    if "docs.google.com/spreadsheets" in text:
        await update.message.reply_text("⏳ Đang kết nối...")
        try:
            gc = get_google_client()
            if not gc:
                await update.message.reply_text("❌ Lỗi Key JSON!")
                return

            sh = gc.open_by_url(text) 
            ws = sh.sheet1
            
            if not ws.acell('A1').value:
                 ws.update(values=[["Ngày", "Món", "Tiền", "Ghi chú"]], range_name='A1:D1')
                 ws.update_acell('F1', "TỔNG QUỸ:")
                 ws.update_acell('G1', "=SUM(C:C)")
                 ws.format("G1", {"textFormat": {"bold": True, "foregroundColor": {"red": 1.0}}})

            if 'books' not in context.user_data: context.user_data['books'] = {}
            book_name = sh.title
            context.user_data['books'][sh.id] = book_name
            context.user_data['current_sheet_id'] = sh.id
            context.user_data['current_book_name'] = book_name
            
            await update.message.reply_text(f"🎉 **ĐÃ THÊM SỔ MỚI!**\nSổ: **{book_name}**\n_(Gõ /so để quản lý)_", parse_mode='Markdown')
        except Exception as e:
            if "403" in str(e):
                await update.message.reply_text("⛔ **Thiếu quyền!**\nGõ `/email` để lấy email Bot và share quyền Editor nhé.")
            else:
                await update.message.reply_text(f"☠️ Lỗi: {str(e)}")
        return

    # 2. GHI TIỀN
    sheet_id = context.user_data.get('current_sheet_id')
    if not sheet_id:
        await update.message.reply_text("⚠️ Chưa có sổ. Gõ `/start` để xem hướng dẫn.")
        return

    try:
        gc = get_google_client()
        ws = gc.open_by_key(sheet_id).sheet1
        
        if text.lower() in ['done', 'chốt']:
            total = ws.acell('G1').value
            await update.message.reply_text(f"✅ **CHỐT SỔ!** Tổng: {total}\n🗑️ Đang xóa...", parse_mode='Markdown')
            ws.batch_clear(['A2:E1000'])
            await update.message.reply_text("✨ Đã xóa dữ liệu.")
            return

        parts = text.split()
        amount = 0; item = ""; date_str = ""
        current_year = datetime.now().year
        
        if len(parts) >= 3 and '/' in parts[0]:
            try:
                dt_temp = datetime.strptime(parts[0], "%d/%m")
                dt_final = dt_temp.replace(year=current_year)
                date_str = dt_final.strftime("%d/%m/%Y")
            except: await update.message.reply_text("⛔ Ngày sai (VD: 30/1)"); return
            amount = float(parts[-1])*1000; item = " ".join(parts[1:-1])
        elif len(parts) >= 2 and parts[-1].replace('.', '').isdigit():
            amount = float(parts[-1])*1000; item = " ".join(parts[:-1])
            date_str = datetime.now().strftime("%d/%m/%Y")
        else:
            await update.message.reply_text("⚠️ Sai cú pháp. Gõ `/help` xem hướng dẫn.")
            return

        col_a = ws.col_values(1)
        next_row = len(col_a) + 1
        ws.update(range_name=f"A{next_row}", values=[[date_str, item, amount]], value_input_option='USER_ENTERED')

        total = ws.acell('G1').value
        if (not total or total == '0') and amount > 0:
            ws.update_acell('G1', "=SUM(C:C)")
            total = ws.acell('G1').value

        await update.message.reply_text(
            f"✅ **{context.user_data.get('current_book_name')}**\n"
            f"Ghi: {item} ({amount:,.0f})\n"
            f"💰 TỔNG: **{total}**", 
            parse_mode='Markdown'
        )

    except Exception as e:
        await update.message.reply_text(f"⚠️ Lỗi: {str(e)}")

if __name__ == '__main__':
    WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL") 
    PORT = int(os.environ.get("PORT", "8443"))

    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('ls', ls_command))
    application.add_handler(CommandHandler('so', list_books_command))
    application.add_handler(CommandHandler('new', new_book_command))
    application.add_handler(CommandHandler('email', email_command)) # Lệnh mới
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    if WEBHOOK_URL:
        application.run_webhook(listen="0.0.0.0", port=PORT, url_path=TOKEN, webhook_url=f"{WEBHOOK_URL}/{TOKEN}")
    else:
        application.run_polling()