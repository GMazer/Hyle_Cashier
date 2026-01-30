import logging
import os
import json
import re
import gspread
from datetime import datetime
from telegram import Update, constants
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
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
    if json_creds:
        try:
            creds_dict = json.loads(json_creds)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        except: return None
    elif os.path.exists("cred.json"):
        creds = ServiceAccountCredentials.from_json_keyfile_name("cred.json", scope)
    else: return None
    return gspread.authorize(creds)

# --- 1. LỆNH START: HƯỚNG DẪN NGƯỜI DÙNG MỚI ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.full_name
    sheet_id = context.user_data.get('sheet_id')

    # Nếu đã kết nối rồi thì chào mừng thôi
    if sheet_id:
        await update.message.reply_text(
            f"👋 Chào mừng **{user_name}** quay lại!\n"
            f"✅ Sổ chi tiêu của bạn vẫn đang hoạt động tốt.\n\n"
            f"👉 Nhập chi tiêu luôn nhé: `30/1 Pho 45`\n"
            f"❓ Cần giúp đỡ? Gõ /help",
            parse_mode='Markdown'
        )
        return

    # Nếu chưa kết nối -> Hiện hướng dẫn chi tiết
    guide_text = (
        f"👋 **Chào {user_name}!** Để tôi giúp bạn quản lý tiền nong nhé.\n\n"
        "Do chính sách bảo mật của Google, bạn cần tạo file Excel (Sheet) của riêng bạn và cấp quyền cho tôi ghi chép.\n\n"
        "🔻 **HÃY LÀM THEO 3 BƯỚC SAU:**\n\n"
        "1️⃣ **Bước 1:** Vào Google Drive tạo 1 file Google Sheet mới (hoặc dùng file cũ).\n\n"
        "2️⃣ **Bước 2:** Bấm nút **Share (Chia sẻ)** trong file đó và dán email này vào:\n"
        f"`{BOT_EMAIL}`\n"
        "👆 *(Chạm vào dòng trên để Copy)*\n"
        "⚠️ **Quan trọng:** Nhớ chọn quyền là **Editor (Người chỉnh sửa)**.\n\n"
        "3️⃣ **Bước 3:** Copy đường Link của file Sheet đó và **gửi vào đây** cho tôi."
    )
    
    await update.message.reply_text(guide_text, parse_mode='Markdown')

# --- 2. LỆNH HELP: DỰ PHÒNG KHI QUÊN ---
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🆘 **TRUNG TÂM TRỢ GIÚP**\n\n"
        "1. **Nhập chi tiêu:**\n"
        "- `30/1 Cafe 20` (Ngày 30/1, Cafe, 20k)\n"
        "- `Com trua 35` (Hôm nay, Cơm, 35k)\n\n"
        "2. **Chốt sổ (Xóa dữ liệu cũ):**\n"
        "- Gõ chữ: `done` hoặc `chốt`\n\n"
        "3. **Kết nối lại sổ:**\n"
        "- Chỉ cần gửi Link Google Sheet mới vào đây là được.\n\n"
        "4. **Email của Bot (để Share):**\n"
        f"`{BOT_EMAIL}`",
        parse_mode='Markdown'
    )

# --- XỬ LÝ TIN NHẮN ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    sheet_id = context.user_data.get('sheet_id')

    # --- NHẬN DIỆN LINK GOOGLE SHEET (KẾT NỐI) ---
    if "docs.google.com/spreadsheets" in text:
        match = re.search(r"/d/([a-zA-Z0-9-_]+)", text)
        if match:
            new_id = match.group(1)
            try:
                gc = get_google_client()
                sh = gc.open_by_key(new_id)
                
                # Setup tiêu đề & công thức
                ws = sh.sheet1
                if not ws.acell('A1').value:
                     ws.update('A1:D1', [["Ngày tháng", "Nội dung", "Số tiền (VNĐ)", "Ghi chú"]])
                     ws.update('F1', "TỔNG CỘNG:")
                     ws.update('G1', "=SUM(C:C)")
                     ws.format("G1", {"textFormat": {"bold": True, "foregroundColor": {"red": 1.0}}})
                
                context.user_data['sheet_id'] = new_id
                context.user_data['sheet_url'] = text
                
                await update.message.reply_text(
                    f"🎉 **KẾT NỐI THÀNH CÔNG!**\n"
                    f"📂 Sổ: [{sh.title}]({text})\n\n"
                    f"✍️ Giờ bạn hãy thử nhập món đầu tiên đi:\n"
                    f"`Cafe 25`",
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
            except Exception as e:
                await update.message.reply_text(
                    "❌ **Không thể truy cập File!**\n"
                    "Có thể bạn quên chưa Share quyền **Editor** cho Bot?\n\n"
                    "Email Bot cần Share:\n"
                    f"`{BOT_EMAIL}`",
                    parse_mode='Markdown'
                )
        else:
            await update.message.reply_text("⚠️ Link không đúng định dạng Google Sheet.")
        return

    # --- NẾU CHƯA CÓ SHEET ---
    if not sheet_id:
        await update.message.reply_text(
            "⚠️ **Chưa kết nối sổ!**\n"
            "Vui lòng gửi **Link Google Sheet** (đã Share quyền Editor) vào đây để bắt đầu.",
            parse_mode='Markdown'
        )
        return

    # --- XỬ LÝ NHẬP LIỆU / CHỐT SỔ (NHƯ CŨ) ---
    try:
        gc = get_google_client()
        ws = gc.open_by_key(sheet_id).sheet1
        
        # Chốt sổ
        if text.lower() in ['done', 'chốt', 'chot']:
            total = ws.acell('G1').value
            await update.message.reply_text(f"✅ **CHỐT SỔ!** Tổng: {total}\n🗑️ Đang dọn dẹp...", parse_mode='Markdown')
            ws.batch_clear(['A2:E1000'])
            await update.message.reply_text("✨ Sổ đã sạch. Sẵn sàng cho tháng mới!")
            return

        # Nhập tiền
        parts = text.split()
        amount = 0; item = ""; date_str = ""
        
        if len(parts) >= 3 and '/' in parts[0]:
            try: date_str = datetime.strptime(parts[0], "%d/%m").strftime("%d/%m/%Y")
            except: await update.message.reply_text("⛔ Ngày sai. Dùng 30/1"); return
            amount = float(parts[-1])*1000; item = " ".join(parts[1:-1])
        elif len(parts) >= 2 and parts[-1].replace('.', '').isdigit():
            amount = float(parts[-1])*1000; item = " ".join(parts[:-1])
            date_str = datetime.now().strftime("%d/%m/%Y")
        else:
            await update.message.reply_text("⚠️ Sai cú pháp. Gõ `/help` để xem hướng dẫn.")
            return

        await update.message.reply_text("⏳...")
        ws.append_row([date_str, item, amount])
        
        # Lấy tổng
        total_str = ws.acell('G1').value or "0"
        await update.message.reply_text(
            f"✅ **Lưu:** {item} ({amount:,.0f}đ)\n💰 **TỔNG:** {total_str} VNĐ", 
            parse_mode='Markdown'
        )

    except Exception as e:
        await update.message.reply_text("⚠️ Lỗi kết nối Google. Thử lại sau.")

if __name__ == '__main__':
    WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL") 
    PORT = int(os.environ.get("PORT", "8443"))

    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command)) # Thêm lệnh help
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    if WEBHOOK_URL:
        application.run_webhook(listen="0.0.0.0", port=PORT, url_path=TOKEN, webhook_url=f"{WEBHOOK_URL}/{TOKEN}")
    else:
        application.run_polling()