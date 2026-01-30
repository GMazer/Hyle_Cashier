import logging
import os
import json
import re
import gspread
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from oauth2client.service_account import ServiceAccountCredentials

# --- CẤU HÌNH ---
TOKEN = '8374820897:AAGLUxuxF5XqlZgHA4O6X8rmMWsJWo4sGqE'
BOT_EMAIL = "bot-chi-tieu@bot-chi-tieu-485902.iam.gserviceaccount.com"

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
        except: return None
    elif os.path.exists("cred.json"):
        creds = ServiceAccountCredentials.from_json_keyfile_name("cred.json", scope)
    else: return None
    return gspread.authorize(creds)

# --- CÁC LỆNH CƠ BẢN ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.full_name
    sheet_id = context.user_data.get('sheet_id')
    if sheet_id:
        await update.message.reply_text(f"👋 Chào {user_name}! Sổ đang mở. Gõ `/ls` để xem lại hoặc nhập tiền luôn.", parse_mode='Markdown')
    else:
        await update.message.reply_text(
            f"👋 **Chào {user_name}!**\nĐể bắt đầu, hãy Share quyền Editor file Sheet cho email:\n`{BOT_EMAIL}`\nRồi gửi Link vào đây.", 
            parse_mode='Markdown'
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🆘 **HƯỚNG DẪN**\n- Nhập: `30/1 Cafe 20`\n- Xem lại: `/ls`\n- Chốt sổ: `done`\n- Email Bot: `{BOT_EMAIL}`",
        parse_mode='Markdown'
    )

# --- LỆNH /LS: XEM LỊCH SỬ (MỚI THÊM VÀO) ---
async def ls_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sheet_id = context.user_data.get('sheet_id')
    if not sheet_id:
        await update.message.reply_text("⚠️ Chưa kết nối sổ. Gửi Link Sheet trước nhé!")
        return

    try:
        await update.message.reply_text("⏳ Đang tải dữ liệu từ Google...")
        gc = get_google_client()
        ws = gc.open_by_key(sheet_id).sheet1
        
        # Lấy toàn bộ dữ liệu
        all_values = ws.get_all_values()
        
        # Nếu chỉ có mỗi dòng tiêu đề (ít hơn 2 dòng)
        if len(all_values) < 2:
            await update.message.reply_text("📭 Sổ chi tiêu đang trống.")
            return

        # Lấy 10 dòng cuối cùng (bỏ qua dòng tiêu đề nếu cần)
        # data_rows là các dòng trừ dòng đầu tiên (tiêu đề)
        data_rows = all_values[1:] 
        last_10 = data_rows[-10:] 

        msg = "🧾 **10 KHOẢN CHI GẦN NHẤT:**\n"
        msg += "-" * 25 + "\n"
        
        for row in last_10:
            # Format: Ngày | Món | Tiền
            # Kiểm tra xem dòng có đủ 3 cột không để tránh lỗi
            d = row[0] if len(row) > 0 else "?"
            n = row[1] if len(row) > 1 else "?"
            m = row[2] if len(row) > 2 else "0"
            
            # Format tiền cho đẹp
            try:
                m_float = float(m.replace(',','').replace('.',''))
                m_fmt = f"{m_float:,.0f}"
            except:
                m_fmt = m

            msg += f"📅 {d} | {n} : **{m_fmt}**\n"
        
        # Lấy tổng cộng từ ô G1
        total = ws.acell('G1').value or "0"
        msg += "-" * 25 + "\n"
        msg += f"💰 **TỔNG CỘNG:** {total} VNĐ"

        await update.message.reply_text(msg, parse_mode='Markdown')

    except Exception as e:
        logging.error(f"Lỗi ls: {e}")
        await update.message.reply_text("⚠️ Lỗi đọc dữ liệu. Thử lại sau.")

# --- XỬ LÝ TIN NHẮN ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    sheet_id = context.user_data.get('sheet_id')

    # Kết nối Link Sheet
    if "docs.google.com/spreadsheets" in text:
        match = re.search(r"/d/([a-zA-Z0-9-_]+)", text)
        if match:
            new_id = match.group(1)
            try:
                gc = get_google_client()
                sh = gc.open_by_key(new_id)
                ws = sh.sheet1
                
                # Cài đặt công thức
                ws.update('F1', "TỔNG CỘNG:")
                ws.update('G1', "=SUM(C:C)")
                if not ws.acell('A1').value:
                     ws.update('A1:D1', [["Ngày tháng", "Nội dung", "Số tiền (VNĐ)", "Ghi chú"]])
                
                context.user_data['sheet_id'] = new_id
                context.user_data['sheet_url'] = text
                await update.message.reply_text(f"✅ Đã kết nối: **{sh.title}**\nGõ `/ls` để xem, hoặc nhập tiền luôn.", parse_mode='Markdown')
            except:
                await update.message.reply_text(f"❌ Lỗi quyền! Share Editor cho:\n`{BOT_EMAIL}`", parse_mode='Markdown')
        else:
            await update.message.reply_text("⚠️ Link sai.")
        return

    if not sheet_id:
        await update.message.reply_text("⚠️ Gửi Link Google Sheet trước.")
        return

    # Xử lý nhập tiền
    try:
        gc = get_google_client()
        ws = gc.open_by_key(sheet_id).sheet1
        
        if text.lower() in ['done', 'chốt', 'chot']:
            total = ws.acell('G1').value
            await update.message.reply_text(f"✅ **CHỐT SỔ!** Tổng: {total}\n🗑️ Đang xóa...", parse_mode='Markdown')
            ws.batch_clear(['A2:E1000'])
            await update.message.reply_text("✨ Sổ đã sạch.")
            return

        parts = text.split()
        amount = 0; item = ""; date_str = ""
        
        if len(parts) >= 3 and '/' in parts[0]:
            try: date_str = datetime.strptime(parts[0], "%d/%m").strftime("%d/%m/%Y")
            except: await update.message.reply_text("⛔ Sai ngày"); return
            amount = float(parts[-1])*1000; item = " ".join(parts[1:-1])
        elif len(parts) >= 2 and parts[-1].replace('.', '').isdigit():
            amount = float(parts[-1])*1000; item = " ".join(parts[:-1])
            date_str = datetime.now().strftime("%d/%m/%Y")
        else:
            await update.message.reply_text("⚠️ Sai cú pháp. Gõ `/help`")
            return

        await update.message.reply_text("⏳...")
        ws.append_row([date_str, item, amount], value_input_option='USER_ENTERED')
        
        total_str = ws.acell('G1').value
        if (not total_str or total_str == '0') and amount > 0:
            ws.update('G1', "=SUM(C:C)")
            total_str = ws.acell('G1').value

        await update.message.reply_text(
            f"✅ **Lưu:** {item} ({amount:,.0f}đ)\n💰 **TỔNG:** {total_str or '0'} VNĐ\n_(Gõ /ls để xem lại)_", 
            parse_mode='Markdown'
        )

    except Exception as e:
        logging.error(f"Lỗi: {e}")
        await update.message.reply_text("⚠️ Lỗi mạng Google.")

if __name__ == '__main__':
    WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL") 
    PORT = int(os.environ.get("PORT", "8443"))

    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('ls', ls_command)) # Đã thêm lại lệnh ls
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    if WEBHOOK_URL:
        application.run_webhook(listen="0.0.0.0", port=PORT, url_path=TOKEN, webhook_url=f"{WEBHOOK_URL}/{TOKEN}")
    else:
        application.run_polling()