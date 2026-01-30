import logging
import os
import json
import re # Thêm thư viện xử lý Link
import gspread
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from oauth2client.service_account import ServiceAccountCredentials

# --- CẤU HÌNH ---
TOKEN = '8374820897:AAGLUxuxF5XqlZgHA4O6X8rmMWsJWo4sGqE'
BOT_EMAIL = "bot-chi-tieu@bot-chi-tieu-485902.iam.gserviceaccount.com" # Email bot của bạn

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def get_google_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    json_creds = os.environ.get("GOOGLE_CREDENTIALS")
    
    if json_creds:
        try:
            creds_dict = json.loads(json_creds)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        except Exception:
            return None
    else:
        if os.path.exists("cred.json"):
            creds = ServiceAccountCredentials.from_json_keyfile_name("cred.json", scope)
        else:
            return None
    return gspread.authorize(creds)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.full_name
    
    # Kiểm tra xem đã kết nối chưa
    if context.user_data.get('sheet_id'):
        await update.message.reply_text(f"👋 Chào {user_name}! Bot đã kết nối sẵn sàng.\nNhập tiền luôn nhé (VD: `30/1 Cafe 20`).")
        return

    # Hướng dẫn kết nối thủ công
    await update.message.reply_text(
        f"👋 Chào {user_name}!\n\n"
        "Do chính sách của Google, tôi không thể tự tạo file mới.\n"
        "**Hãy giúp tôi kết nối theo 3 bước sau:**\n\n"
        "1️⃣ Tạo 1 file Google Sheet của bạn.\n"
        "2️⃣ Bấm Share (Chia sẻ) cho email này (Quyền Editor):\n"
        f"`{BOT_EMAIL}`\n"
        "(Bấm vào email để copy)\n\n"
        "3️⃣ **Copy Link của file Sheet đó và gửi vào đây cho tôi.**",
        parse_mode='Markdown'
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    sheet_id = context.user_data.get('sheet_id')

    # --- TRƯỜNG HỢP 1: NGƯỜI DÙNG GỬI LINK GOOGLE SHEET ---
    if "docs.google.com/spreadsheets" in text:
        try:
            # Lấy ID từ đường link
            # Link dạng: .../d/1A2B3C4D.../edit...
            match = re.search(r"/d/([a-zA-Z0-9-_]+)", text)
            if match:
                new_id = match.group(1)
                
                # Thử kết nối
                gc = get_google_client()
                if not gc:
                    await update.message.reply_text("⚠️ Lỗi cấu hình Bot (Thiếu file cred.json).")
                    return
                
                sh = gc.open_by_key(new_id)
                
                # Cài đặt tiêu đề nếu chưa có
                ws = sh.sheet1
                if not ws.acell('A1').value:
                     ws.update('A1:D1', [["Ngày tháng", "Nội dung", "Số tiền (VNĐ)", "Ghi chú"]])
                     ws.update('F1', "TỔNG CỘNG:")
                     ws.update('G1', "=SUM(C:C)")
                
                # Lưu ID vào bộ nhớ
                context.user_data['sheet_id'] = new_id
                context.user_data['sheet_url'] = text
                
                await update.message.reply_text(f"✅ **Kết nối thành công!**\nSổ: {sh.title}\n\nGiờ bạn có thể nhập chi tiêu (VD: `Com trua 35`).", parse_mode='Markdown')
            else:
                await update.message.reply_text("⚠️ Link không hợp lệ. Hãy gửi đúng link Google Sheet.")
        except Exception as e:
            await update.message.reply_text(f"⚠️ Không thể mở file. Bạn đã Share quyền Editor cho email `{BOT_EMAIL}` chưa?", parse_mode='Markdown')
        return

    # --- TRƯỜNG HỢP 2: CHƯA KẾT NỐI ---
    if not sheet_id:
        await update.message.reply_text("⚠️ Bạn chưa kết nối Sổ chi tiêu.\n👉 Hãy gửi **Link Google Sheet** (đã share quyền Editor) vào đây trước.")
        return

    # --- TRƯỜNG HỢP 3: XỬ LÝ NHẬP TIỀN / RESET (GIỮ NGUYÊN CODE CŨ) ---
    try:
        gc = get_google_client()
        sh = gc.open_by_key(sheet_id)
        ws = sh.sheet1
    except:
        await update.message.reply_text("⚠️ Mất kết nối Google Sheet. Hãy gửi lại Link để kết nối lại.")
        return

    # Logic xử lý DONE (Xóa dữ liệu)
    if text.lower() in ['done', 'chốt', 'chot']:
        try:
            final_total = ws.acell('G1').value
            await update.message.reply_text(f"✅ **CHỐT SỔ!** Tổng: {final_total}\n🗑️ Đang xóa dữ liệu cũ...", parse_mode='Markdown')
            ws.batch_clear(['A2:E1000']) 
            await update.message.reply_text("✨ Đã làm sạch sổ. Sẵn sàng cho tháng mới!")
            return
        except Exception as e:
            await update.message.reply_text("⚠️ Lỗi khi xóa.")
            return

    # Logic xử lý nhập tiền
    try:
        parts = text.split()
        amount = 0
        item_name = ""
        date_str = ""
        
        if len(parts) >= 3 and '/' in parts[0]:
            try:
                date_str = datetime.strptime(parts[0], "%d/%m").strftime("%d/%m/%Y")
            except ValueError:
                await update.message.reply_text("⛔ Ngày sai. Dùng dạng 30/1")
                return
            amount = float(parts[-1]) * 1000
            item_name = " ".join(parts[1:-1])
        elif len(parts) >= 2 and parts[-1].replace('.', '').isdigit():
            amount = float(parts[-1]) * 1000
            item_name = " ".join(parts[:-1])
            date_str = datetime.now().strftime("%d/%m/%Y")
        else:
            await update.message.reply_text("⚠️ Sai cú pháp! Nhập: `Tên món + Giá tiền`")
            return

        # Ghi và báo cáo
        await update.message.reply_text("⏳ Đang lưu...")
        ws.append_row([date_str, item_name, amount])
        
        # Đọc tổng từ ô G1
        total_str = ws.acell('G1').value 
        formatted_total = total_str if total_str else "0"
        
        await update.message.reply_text(
            f"✅ **Đã ghi:** {item_name} ({amount:,.0f}đ)\n"
            f"💰 **TỔNG QUỸ:** {formatted_total} VNĐ", 
            parse_mode='Markdown'
        )

    except Exception as e:
        logging.error(f"Lỗi: {e}")
        await update.message.reply_text("⚠️ Lỗi xử lý.")

if __name__ == '__main__':
    WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL") 
    PORT = int(os.environ.get("PORT", "8443"))

    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    if WEBHOOK_URL:
        application.run_webhook(
            listen="0.0.0.0", port=PORT, url_path=TOKEN, webhook_url=f"{WEBHOOK_URL}/{TOKEN}"
        )
    else:
        application.run_polling()