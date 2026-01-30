import logging
import os
import json
import gspread
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from oauth2client.service_account import ServiceAccountCredentials

# --- CẤU HÌNH ---
TOKEN = '8374820897:AAGLUxuxF5XqlZgHA4O6X8rmMWsJWo4sGqE'  # Token của bạn

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- HÀM KẾT NỐI GOOGLE (Chạy được cả Local và Render) ---
def get_google_client():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    
    # 1. Ưu tiên lấy từ Biến môi trường (Trên Render)
    json_creds = os.environ.get("GOOGLE_CREDENTIALS")
    
    if json_creds:
        try:
            creds_dict = json.loads(json_creds)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        except Exception as e:
            logging.error(f"Lỗi đọc biến môi trường: {e}")
            return None
    else:
        # 2. Nếu không có, tìm file cred.json (Trên máy cá nhân)
        if os.path.exists("cred.json"):
            creds = ServiceAccountCredentials.from_json_keyfile_name("cred.json", scope)
        else:
            logging.error("Không tìm thấy chứng chỉ Google (cred.json hoặc ENV)")
            return None

    return gspread.authorize(creds)

# --- CÁC HÀM XỬ LÝ BOT ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # Đặt tên file theo ID để đảm bảo duy nhất và dễ tìm lại
    sheet_name = f"ChiTieu_Bot_{user.id}" 
    
    await update.message.reply_text("⏳ Đang kết nối dữ liệu của bạn...")

    try:
        gc = get_google_client()
        if not gc:
            await update.message.reply_text("⚠️ Lỗi kết nối Google.")
            return

        # --- LOGIC THÔNG MINH MỚI ---
        try:
            # 1. Cố gắng mở file cũ nếu đã tồn tại
            sh = gc.open(sheet_name)
            await update.message.reply_text(f"👋 Chào mừng trở lại! Đã tìm thấy sổ cũ của bạn.")
        except gspread.exceptions.SpreadsheetNotFound:
            # 2. Nếu không tìm thấy (User mới), thì tạo file mới
            sh = gc.create(sheet_name)
            sh.share(None, perm_type='anyone', role='writer') # Share quyền
            
            # Tạo dòng tiêu đề
            worksheet = sh.sheet1
            worksheet.append_row(["Ngày tháng", "Nội dung", "Số tiền (VNĐ)", "Ghi chú"])
            await update.message.reply_text(f"🆕 Đã tạo sổ chi tiêu mới cho bạn.")
        # -----------------------------

        # Lưu lại ID để dùng cho các tin nhắn sau
        context.user_data['sheet_id'] = sh.id
        context.user_data['sheet_url'] = sh.url

        await update.message.reply_text(
            f"📂 Link sổ của bạn: [Bấm vào đây]({sh.url})\n\n"
            f"✍️ Hãy nhập chi tiêu (VD: `30/1 Cafe 25`)",
            parse_mode='Markdown',
            disable_web_page_preview=True
        )

    except Exception as e:
        logging.error(f"Lỗi start: {e}")
        await update.message.reply_text("⚠️ Có lỗi xảy ra, vui lòng thử lại sau.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    # Kiểm tra xem User đã có sổ chưa (đã chạy /start chưa)
    sheet_id = context.user_data.get('sheet_id')
    if not sheet_id:
        await update.message.reply_text("⚠️ Bạn chưa có sổ chi tiêu. Hãy bấm /start để tạo sổ mới trước nhé!")
        return

    # Logic xử lý tin nhắn
    try:
        parts = text.split()
        amount = 0
        item_name = ""
        date_str = ""
        
        # Trường hợp 1: Có ngày tháng (VD: 30/1 Cafe 20)
        if len(parts) >= 3 and '/' in parts[0]:
            try:
                date_str = datetime.strptime(parts[0], "%d/%m").strftime("%d/%m/%Y")
            except ValueError:
                await update.message.reply_text("⛔ Sai ngày. Nhập dạng 30/1")
                return
            amount = float(parts[-1]) * 1000
            item_name = " ".join(parts[1:-1])

        # Trường hợp 2: Không có ngày (VD: Cafe 20 -> Mặc định hôm nay)
        elif len(parts) >= 2 and parts[-1].replace('.', '').isdigit():
            amount = float(parts[-1]) * 1000
            item_name = " ".join(parts[:-1])
            date_str = datetime.now().strftime("%d/%m/%Y")
            
        else:
            await update.message.reply_text("⚠️ Sai cú pháp! Hãy nhập: `Món đồ + Giá tiền`")
            return

        # GHI VÀO GOOGLE SHEET
        await update.message.reply_text("⏳ Đang ghi vào sổ...")
        
        gc = get_google_client()
        sh = gc.open_by_key(sheet_id)
        worksheet = sh.sheet1
        
        # Thêm dòng mới: Ngày | Tên | Tiền
        worksheet.append_row([date_str, item_name, amount])

        await update.message.reply_text(
            f"✅ **Đã lưu!**\n"
            f"📅 {date_str} | 🍜 {item_name} | 💸 {amount:,.0f}đ\n"
            f"👉 [Xem sổ tại đây]({context.user_data['sheet_url']})",
            parse_mode='Markdown',
            disable_web_page_preview=True
        )

    except Exception as e:
        logging.error(f"Lỗi ghi sheet: {e}")
        await update.message.reply_text("⚠️ Lỗi khi ghi vào Sheet. Có thể mạng chậm, hãy thử lại.")

if __name__ == '__main__':
    # --- PHẦN TỰ ĐỘNG NHẬN DIỆN MÔI TRƯỜNG ---
    WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL") 
    PORT = int(os.environ.get("PORT", "8443"))

    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    if WEBHOOK_URL:
        print(f"🚀 Đang chạy trên Render (Port {PORT})...")
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{TOKEN}"
        )
    else:
        print("💻 Đang chạy trên máy cá nhân (Polling)...")
        application.run_polling()