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

# --- LỆNH START ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.full_name
    
    # Khởi tạo danh sách sổ nếu chưa có
    if 'books' not in context.user_data:
        context.user_data['books'] = {} # Cấu trúc: {'SheetID': 'Tên Sổ'}
    
    current_book = context.user_data.get('current_book_name', 'Chưa chọn')

    msg = (
        f"👋 **Chào {user_name}!**\n\n"
        f"📂 Sổ đang dùng: **{current_book}**\n\n"
        "🔹 **Thêm sổ mới:**\n"
        "   Gửi Link Google Sheet (đã Share Editor) vào đây.\n"
        "   _Hoặc gõ `/new TênSổ` để tạo mới._\n\n"
        "🔹 **Đổi sổ:** Gõ `/so` để hiện danh sách.\n"
        "🔹 **Ghi tiền:** Nhập `30/1 Cafe 25`"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

# --- LỆNH HELP ---
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📚 **HƯỚNG DẪN**\n\n"
        "1️⃣ **Quản lý Sổ:**\n"
        "• Gửi Link Sheet: Thêm sổ vào danh sách.\n"
        "• `/so`: Hiện menu chọn sổ.\n"
        "• `/new QuyDen`: Tạo sổ mới tên là 'QuyDen'.\n\n"
        "2️⃣ **Ghi chép:**\n"
        "• `Cafe 25` (Mặc định hôm nay)\n"
        "• `30/1 Cafe 25` (Tự thêm năm hiện tại)\n\n"
        "3️⃣ **Khác:**\n"
        "• `/ls`: Xem 10 khoản mới nhất.\n"
        "• `done`: Chốt sổ (Xóa dữ liệu cũ)."
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

# --- LỆNH NEW: TẠO SỔ MỚI ---
async def new_book_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("⚠️ Hãy nhập tên sổ. VD: `/new QuyDen`", parse_mode='Markdown')
        return
    
    book_name = " ".join(args)
    await update.message.reply_text(f"⏳ Đang cố gắng tạo sổ **{book_name}**...")

    try:
        gc = get_google_client()
        # Tạo file mới
        sh = gc.create(book_name)
        # Share quyền
        sh.share(None, perm_type='anyone', role='writer')
        
        # Setup tiêu đề
        ws = sh.sheet1
        ws.update(values=[["Ngày", "Món", "Tiền", "Ghi chú"]], range_name='A1:D1')
        ws.update_acell('F1', "TỔNG QUỸ:")
        ws.update_acell('G1', "=SUM(C:C)")
        ws.format("G1", {"textFormat": {"bold": True, "foregroundColor": {"red": 1.0}}})

        # Lưu vào danh sách
        if 'books' not in context.user_data: context.user_data['books'] = {}
        context.user_data['books'][sh.id] = book_name
        context.user_data['current_sheet_id'] = sh.id
        context.user_data['current_book_name'] = book_name

        await update.message.reply_text(
            f"✅ **Tạo thành công!**\nSổ: [{book_name}]({sh.url})\nĐã chuyển sang sổ này.", 
            parse_mode='Markdown', disable_web_page_preview=True
        )

    except Exception as e:
        err = str(e)
        if "403" in err:
            await update.message.reply_text(
                "⛔ **Lỗi quyền hạn (Google 403):**\n"
                "Bot mới (Service Account) thường không có dung lượng để tự tạo file.\n\n"
                "👉 **Cách khắc phục:**\n"
                "1. Bạn tự tạo file trên Google Drive của bạn.\n"
                f"2. Share Editor cho email: `{BOT_EMAIL}`\n"
                "3. Copy Link gửi vào đây.",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(f"⚠️ Lỗi: {err}")

# --- LỆNH SO: MENU CHUYỂN SỔ ---
async def list_books_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    books = context.user_data.get('books', {})
    if not books:
        await update.message.reply_text("⚠️ Bạn chưa có sổ nào. Hãy gửi Link Sheet vào đây.")
        return

    current_id = context.user_data.get('current_sheet_id')
    
    keyboard = []
    for bid, bname in books.items():
        # Đánh dấu sổ đang chọn
        label = f"✅ {bname}" if bid == current_id else bname
        # Callback data format: "SELECT_BOOK|sheet_id"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"SELECT|{bid}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📂 **CHỌN SỔ CHI TIÊU:**", reply_markup=reply_markup, parse_mode='Markdown')

# --- XỬ LÝ BẤM NÚT CHỌN SỔ ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer() # Báo cho Telegram biết đã bấm

    data = query.data.split("|")
    if data[0] == "SELECT":
        selected_id = data[1]
        books = context.user_data.get('books', {})
        book_name = books.get(selected_id, "Không tên")

        # Cập nhật sổ hiện tại
        context.user_data['current_sheet_id'] = selected_id
        context.user_data['current_book_name'] = book_name

        await query.edit_message_text(f"✅ Đã chuyển sang sổ: **{book_name}**", parse_mode='Markdown')

# --- LỆNH LS ---
async def ls_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sheet_id = context.user_data.get('current_sheet_id')
    if not sheet_id:
        await update.message.reply_text("⚠️ Chưa chọn sổ nào. Gõ `/so` hoặc gửi Link.")
        return

    try:
        await update.message.reply_text("⏳ Đang đọc sổ...")
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
        msg += "-"*20 + f"\n💰 **TỔNG: {total}**"
        await update.message.reply_text(msg, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"⚠️ Lỗi đọc sổ: {str(e)}")

# --- XỬ LÝ TIN NHẮN ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    # === 1. THÊM SỔ BẰNG LINK ===
    if "docs.google.com/spreadsheets" in text:
        await update.message.reply_text("⏳ Đang kết nối...")
        try:
            gc = get_google_client()
            if not gc:
                await update.message.reply_text("❌ Lỗi Key JSON!")
                return

            sh = gc.open_by_url(text) 
            ws = sh.sheet1
            
            # Setup nếu file mới
            if not ws.acell('A1').value:
                 ws.update(values=[["Ngày", "Món", "Tiền", "Ghi chú"]], range_name='A1:D1')
                 ws.update_acell('F1', "TỔNG QUỸ:")
                 ws.update_acell('G1', "=SUM(C:C)")
                 ws.format("G1", {"textFormat": {"bold": True, "foregroundColor": {"red": 1.0}}})

            # Lưu vào danh sách
            if 'books' not in context.user_data: context.user_data['books'] = {}
            
            book_name = sh.title
            context.user_data['books'][sh.id] = book_name
            context.user_data['current_sheet_id'] = sh.id
            context.user_data['current_book_name'] = book_name
            
            await update.message.reply_text(
                f"🎉 **ĐÃ THÊM SỔ MỚI!**\n"
                f"Tên: **{book_name}**\n"
                f"Đã đặt làm sổ mặc định.\n"
                f"_(Gõ /so để đổi sổ khác bất cứ lúc nào)_", 
                parse_mode='Markdown'
            )
        except Exception as e:
            if "403" in str(e):
                await update.message.reply_text("⛔ **Thiếu quyền!** Hãy Share Editor cho email Bot.")
            else:
                await update.message.reply_text(f"☠️ Lỗi: {str(e)}")
        return

    # === 2. GHI TIỀN ===
    sheet_id = context.user_data.get('current_sheet_id')
    if not sheet_id:
        await update.message.reply_text("⚠️ Chưa chọn sổ. Gửi Link Sheet hoặc gõ `/new`.")
        return

    try:
        gc = get_google_client()
        ws = gc.open_by_key(sheet_id).sheet1
        
        # Chốt sổ
        if text.lower() in ['done', 'chốt', 'chot']:
            total = ws.acell('G1').value
            await update.message.reply_text(f"✅ **CHỐT SỔ!** Tổng: {total}\n🗑️ Đang xóa...", parse_mode='Markdown')
            ws.batch_clear(['A2:E1000'])
            await update.message.reply_text("✨ Đã xóa dữ liệu.")
            return

        parts = text.split()
        amount = 0; item = ""; date_str = ""
        current_year = datetime.now().year # Lấy năm hiện tại
        
        # --- LOGIC XỬ LÝ NGÀY THÁNG THÔNG MINH ---
        if len(parts) >= 3 and '/' in parts[0]:
            try:
                # Parse ngày tháng (ví dụ 30/1)
                dt_temp = datetime.strptime(parts[0], "%d/%m")
                # Gán năm hiện tại vào
                dt_final = dt_temp.replace(year=current_year)
                date_str = dt_final.strftime("%d/%m/%Y")
            except ValueError:
                await update.message.reply_text("⛔ Sai ngày. (VD: 30/1)"); return
            
            amount = float(parts[-1])*1000
            item = " ".join(parts[1:-1])

        elif len(parts) >= 2 and parts[-1].replace('.', '').isdigit():
            amount = float(parts[-1])*1000
            item = " ".join(parts[:-1])
            date_str = datetime.now().strftime("%d/%m/%Y")
        else:
            await update.message.reply_text("⚠️ Sai cú pháp. VD: `Cafe 20`")
            return

        # Ghi dữ liệu (Dùng cách đếm dòng để không nhảy cột)
        col_a = ws.col_values(1)
        next_row = len(col_a) + 1
        
        ws.update(
            range_name=f"A{next_row}", 
            values=[[date_str, item, amount]], 
            value_input_option='USER_ENTERED'
        )

        # Fix tổng
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
    
    # Đăng ký các lệnh
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('ls', ls_command))
    application.add_handler(CommandHandler('so', list_books_command)) # Lệnh mới
    application.add_handler(CommandHandler('new', new_book_command)) # Lệnh mới
    
    # Xử lý bấm nút
    application.add_handler(CallbackQueryHandler(button_callback))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    if WEBHOOK_URL:
        application.run_webhook(listen="0.0.0.0", port=PORT, url_path=TOKEN, webhook_url=f"{WEBHOOK_URL}/{TOKEN}")
    else:
        application.run_polling()