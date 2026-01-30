import logging
import os
import json
import gspread
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from oauth2client.service_account import ServiceAccountCredentials

# --- CẤU HÌNH (GIỮ NGUYÊN) ---
TOKEN = '8374820897:AAGLUxuxF5XqlZgHA4O6X8rmMWsJWo4sGqE'
BOT_EMAIL = "bot-chi-tieu@bot-chi-tieu-485902.iam.gserviceaccount.com"

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- HÀM KẾT NỐI GOOGLE (GIỮ NGUYÊN) ---
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

# --- LỆNH START: HƯỚNG DẪN TẬN TÌNH ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.full_name
    sheet_id = context.user_data.get('sheet_id')
    
    # Nếu đã kết nối rồi
    if sheet_id:
        await update.message.reply_text(
            f"👋 **Chào {user_name}!**\n"
            f"Bot vẫn đang hoạt động tốt trên sổ của bạn.\n\n"
            f"💡 **Gợi ý:** Gõ `/ls` để xem lại chi tiêu hoặc nhập tiền luôn nhé!", 
            parse_mode='Markdown'
        )
        return

    # Nếu là người mới -> Hướng dẫn từng bước
    msg = (
        f"👋 **Xin chào {user_name}! Mình là Trợ lý Tài chính cá nhân.**\n\n"
        "Để mình giúp bạn ghi chép tiền nong, chúng ta cần kết nối với Google Sheet (Sổ cái) của bạn. Hãy làm theo 3 bước dễ ợt này nhé:\n\n"
        "1️⃣ **Bước 1:** Vào Google Drive tạo một file Google Sheet mới (hoặc mở file cũ).\n\n"
        "2️⃣ **Bước 2:** Bấm nút **Share (Chia sẻ)** góc phải màn hình, và dán email này vào:\n"
        f"`{BOT_EMAIL}`\n"
        "👆 _(Bấm vào dòng trên để copy nhanh)_\n"
        "⚠️ *Lưu ý: Nhớ chọn quyền là **Editor (Người chỉnh sửa)** nhé!*\n\n"
        "3️⃣ **Bước 3:** Copy đường Link của file Sheet đó và **Gửi vào đây cho mình**."
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

# --- LỆNH HELP: CẨM NANG SỬ DỤNG ---
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📚 **HƯỚNG DẪN SỬ DỤNG**\n\n"
        "**1. Ghi chép chi tiêu:**\n"
        "• Cách nhanh: `Tên món + Tiền`\n"
        "   VD: `Cafe 25` (Hôm nay uống Cafe 25k)\n"
        "   VD: `Bun cha 40` (Hôm nay ăn Bún chả 40k)\n"
        "• Kèm ngày tháng: `Ngày/Tháng + Tên món + Tiền`\n"
        "   VD: `30/1 Dien nuoc 500` (Ngày 30/1 đóng 500k)\n\n"
        "**2. Xem báo cáo:**\n"
        "• Gõ lệnh: `/ls`\n"
        "   (Để xem 10 khoản gần nhất và Tổng tiền trong quỹ)\n\n"
        "**3. Các lệnh khác:**\n"
        "• Gõ `chốt` hoặc `done`: Để xóa sạch dữ liệu cũ, bắt đầu tháng mới.\n"
        "• Gửi Link Google Sheet mới: Để đổi sang sổ khác."
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

# --- LỆNH LS: XEM DANH SÁCH ---
async def ls_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sheet_id = context.user_data.get('sheet_id')
    if not sheet_id:
        await update.message.reply_text("⚠️ Bạn chưa kết nối sổ. Hãy gửi Link Google Sheet trước nhé!")
        return

    try:
        await update.message.reply_text("⏳ Đang lấy dữ liệu...")
        gc = get_google_client()
        ws = gc.open_by_key(sheet_id).sheet1
        vals = ws.get_all_values()
        
        if len(vals) < 2:
            await update.message.reply_text("📭 Sổ chi tiêu của bạn đang trống trơn.")
            return

        # Lấy 10 dòng cuối
        last_10 = vals[1:][-10:]
        
        msg = "🧾 **10 KHOẢN CHI GẦN NHẤT:**\n" + "-"*25 + "\n"
        for r in last_10:
            d = r[0] if len(r)>0 else ""
            n = r[1] if len(r)>1 else ""
            m = r[2] if len(r)>2 else "0"
            
            # Format tiền (thêm dấu phẩy cho dễ đọc)
            try:
                m_fmt = "{:,.0f}".format(float(m.replace(',','').replace('.','')))
            except: m_fmt = m
            
            msg += f"📅 {d} | {n} : **{m_fmt}**\n"
            
        total = ws.acell('G1').value or "0"
        msg += "-"*25 + f"\n💰 **TỔNG CỘNG:** {total} VNĐ"
        
        await update.message.reply_text(msg, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text("⚠️ Có lỗi khi đọc dữ liệu. Thử lại sau nhé!")

# --- XỬ LÝ TIN NHẮN (LOGIC CHÍNH) ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    sheet_id = context.user_data.get('sheet_id')

    # === TRƯỜNG HỢP 1: NGƯỜI DÙNG GỬI LINK SHEET ===
    if "docs.google.com/spreadsheets" in text:
        await update.message.reply_text("⏳ Đang kết nối với sổ của bạn...")
        try:
            gc = get_google_client()
            if not gc:
                await update.message.reply_text("❌ Lỗi hệ thống: Không tìm thấy Key bảo mật!")
                return

            sh = gc.open_by_url(text) 
            ws = sh.sheet1
            
            # --- SỬA LỖI QUAN TRỌNG (Dùng update_acell) ---
            # Kiểm tra nếu file trắng thì tạo tiêu đề
            if not ws.acell('A1').value:
                 # Tạo tiêu đề cột
                 ws.update([["Ngày", "Món", "Tiền", "Ghi chú"]], 'A1:D1') 
                 # Tạo ô tính tổng (Dùng update_acell để tránh lỗi 400)
                 ws.update_acell('F1', "TỔNG QUỸ:")
                 ws.update_acell('G1', "=SUM(C:C)")
                 # Tô màu đỏ cho ô Tổng tiền
                 ws.format("G1", {"textFormat": {"bold": True, "foregroundColor": {"red": 1.0}}})

            context.user_data['sheet_id'] = sh.id
            context.user_data['sheet_url'] = text
            
            await update.message.reply_text(
                f"🎉 **KẾT NỐI THÀNH CÔNG!**\n\n"
                f"📂 Tên sổ: **{sh.title}**\n"
                f"✍️ Bây giờ bạn hãy thử nhập món đầu tiên đi.\n"
                f"Ví dụ: `Cafe 25`", 
                parse_mode='Markdown'
            )
        except Exception as e:
            # Thông báo lỗi thân thiện hơn
            err = str(e)
            if "403" in err:
                await update.message.reply_text("⛔ **Chưa cấp quyền!**\nBot không vào được file. Bạn hãy kiểm tra xem đã Share quyền **Editor** cho email của Bot chưa nhé.")
            else:
                await update.message.reply_text(f"☠️ Lỗi kết nối: {err}")
        return

    # === TRƯỜNG HỢP 2: NHẬP TIỀN HOẶC LỆNH KHÁC ===
    if not sheet_id:
        await update.message.reply_text("⚠️ Bạn chưa kết nối sổ nào cả.\n👉 Hãy gửi **Link Google Sheet** vào đây để bắt đầu.")
        return

    try:
        gc = get_google_client()
        ws = gc.open_by_key(sheet_id).sheet1
        
        # --- LỆNH CHỐT SỔ ---
        if text.lower() in ['done', 'chốt', 'chot']:
            total = ws.acell('G1').value
            await update.message.reply_text(f"✅ **CHỐT SỔ THÀNH CÔNG!**\n💰 Tổng chi tiêu đợt này: **{total}**\n🗑️ Đang dọn dẹp dữ liệu cũ...", parse_mode='Markdown')
            ws.batch_clear(['A2:E1000'])
            await update.message.reply_text("✨ Sổ đã sạch sẽ. Sẵn sàng cho khởi đầu mới!")
            return

        # --- XỬ LÝ NHẬP TIỀN ---
        parts = text.split()
        amount = 0; item = ""; date_str = ""
        
        # Logic tách chữ: "30/1 Cafe 20"
        if len(parts) >= 3 and '/' in parts[0]:
            try: date_str = datetime.strptime(parts[0], "%d/%m").strftime("%d/%m/%Y")
            except: await update.message.reply_text("⛔ Ngày sai định dạng. Hãy dùng: 30/1"); return
            amount = float(parts[-1])*1000; item = " ".join(parts[1:-1])
        # Logic tách chữ: "Cafe 20" (Mặc định hôm nay)
        elif len(parts) >= 2 and parts[-1].replace('.', '').isdigit():
            amount = float(parts[-1])*1000; item = " ".join(parts[:-1])
            date_str = datetime.now().strftime("%d/%m/%Y")
        else:
            await update.message.reply_text("⚠️ Sai cú pháp rồi.\nVí dụ đúng: `Cafe 20` hoặc `30/1 Cafe 20`\nGõ `/help` để xem hướng dẫn.")
            return

        # Ghi vào Sheet
        ws.append_row([date_str, item, amount], value_input_option='USER_ENTERED')
        
        # Tự động sửa lỗi mất công thức tính tổng
        total = ws.acell('G1').value
        if (not total or total == '0') and amount > 0:
            ws.update_acell('G1', "=SUM(C:C)")
            total = ws.acell('G1').value

        await update.message.reply_text(
            f"✅ **Đã lưu:** {item}\n"
            f"💸 Số tiền: **{amount:,.0f} đ**\n"
            f"💰 **TỔNG QUỸ:** {total} VNĐ", 
            parse_mode='Markdown'
        )

    except Exception as e:
        await update.message.reply_text(f"⚠️ Có lỗi xảy ra khi lưu: {str(e)}")

if __name__ == '__main__':
    WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL") 
    PORT = int(os.environ.get("PORT", "8443"))

    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('ls', ls_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    if WEBHOOK_URL:
        application.run_webhook(listen="0.0.0.0", port=PORT, url_path=TOKEN, webhook_url=f"{WEBHOOK_URL}/{TOKEN}")
    else:
        application.run_polling()