import logging
import os
import json
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

# --- LỆNH START: HƯỚNG DẪN CHI TIẾT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.full_name
    sheet_id = context.user_data.get('sheet_id')
    
    if sheet_id:
        await update.message.reply_text(f"👋 Chào {user_name}! Sổ đang mở, bạn cứ nhập tiền thoải mái nhé.", parse_mode='Markdown')
        return

    # Hướng dẫn cực kỳ dễ hiểu cho người mới
    msg = (
        f"👋 **Chào {user_name}! Mình là Trợ lý Sổ Thu Chi.**\n\n"
        "Để mình giúp bạn ghi tiền nong, chúng ta cần một cuốn sổ (Google Sheet). Hãy làm 3 bước này nhé:\n\n"
        "1️⃣ **Tạo sổ:** Vào Google Drive tạo 1 file Google Sheet mới.\n\n"
        "2️⃣ **Cấp quyền:** Bấm nút **Share (Chia sẻ)** góc phải file đó, rồi dán email này vào:\n"
        f"`{BOT_EMAIL}`\n"
        "👆 _(Chạm vào dòng trên để copy email)_\n"
        "⚠️ *Nhớ chọn quyền là **Editor (Người chỉnh sửa)** nhé!*\n\n"
        "3️⃣ **Kết nối:** Copy đường Link của file Sheet đó và **Gửi vào đây cho mình**."
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

# --- LỆNH HELP ---
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📚 **SỔ TAY HƯỚNG DẪN**\n\n"
        "✏️ **Cách ghi tiền:**\n"
        "• `Tên món + Tiền` (Mặc định hôm nay)\n"
        "   VD: `Pho bo 40` (Phở bò 40k)\n"
        "• `Ngày + Tên món + Tiền`\n"
        "   VD: `30/1 Luong ve 5000`\n\n"
        "📊 **Các lệnh khác:**\n"
        "• `/ls` : Xem 10 khoản gần nhất.\n"
        "• `done` : Xóa sổ cũ, bắt đầu tháng mới.\n"
        "• Gửi Link Sheet mới : Để đổi sổ khác."
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

# --- LỆNH LS ---
async def ls_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sheet_id = context.user_data.get('sheet_id')
    if not sheet_id:
        await update.message.reply_text("⚠️ Chưa kết nối sổ. Gửi Link Sheet trước nhé!")
        return

    try:
        await update.message.reply_text("⏳ Đang đọc sổ...")
        gc = get_google_client()
        ws = gc.open_by_key(sheet_id).sheet1
        vals = ws.get_all_values()
        
        if len(vals) < 2:
            await update.message.reply_text("📭 Sổ đang trắng tinh.")
            return

        last_10 = vals[1:][-10:]
        msg = "🧾 **CHI TIÊU GẦN ĐÂY:**\n" + "-"*22 + "\n"
        for r in last_10:
            d = r[0] if len(r)>0 else ""
            n = r[1] if len(r)>1 else ""
            m = r[2] if len(r)>2 else "0"
            try: m_fmt = "{:,.0f}".format(float(m.replace(',','').replace('.','')))
            except: m_fmt = m
            msg += f"📅 {d} | {n} : **{m_fmt}**\n"
            
        total = ws.acell('G1').value or "0"
        msg += "-"*22 + f"\n💰 **TỔNG QUỸ:** {total} VNĐ"
        await update.message.reply_text(msg, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text("⚠️ Lỗi đọc sổ. Thử lại sau.")

# --- XỬ LÝ TIN NHẮN CHÍNH ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    sheet_id = context.user_data.get('sheet_id')

    # === 1. LOGIC NHẬN LINK ===
    if "docs.google.com/spreadsheets" in text:
        await update.message.reply_text("⏳ Đang kết nối...")
        try:
            gc = get_google_client()
            if not gc:
                await update.message.reply_text("❌ Lỗi Key JSON trên Render!")
                return

            sh = gc.open_by_url(text) 
            ws = sh.sheet1
            
            # Khởi tạo tiêu đề nếu file trống
            if not ws.acell('A1').value:
                 ws.update(values=[["Ngày", "Món", "Tiền", "Ghi chú"]], range_name='A1:D1')
                 ws.update_acell('F1', "TỔNG QUỸ:")
                 ws.update_acell('G1', "=SUM(C:C)")
                 ws.format("G1", {"textFormat": {"bold": True, "foregroundColor": {"red": 1.0}}})

            context.user_data['sheet_id'] = sh.id
            context.user_data['sheet_url'] = text
            
            await update.message.reply_text(
                f"🎉 **THÀNH CÔNG!**\nSổ: **{sh.title}**\n\n✍️ Nhập thử món đầu tiên đi:\n`Test 1`", 
                parse_mode='Markdown'
            )
        except Exception as e:
            if "403" in str(e):
                await update.message.reply_text("⛔ **Thiếu quyền!**\nHãy kiểm tra lại xem đã Share quyền **Editor** cho email Bot chưa nhé.")
            else:
                await update.message.reply_text(f"☠️ Lỗi: {str(e)}")
        return

    if not sheet_id:
        await update.message.reply_text("⚠️ Bạn chưa có sổ. Hãy gửi **Link Google Sheet** vào đây trước.")
        return

    # === 2. LOGIC NHẬP TIỀN / RESET ===
    try:
        gc = get_google_client()
        ws = gc.open_by_key(sheet_id).sheet1
        
        # --- LỆNH DONE/CHỐT ---
        if text.lower() in ['done', 'chốt', 'chot']:
            total = ws.acell('G1').value
            await update.message.reply_text(f"✅ **CHỐT SỔ!** Tổng: {total}\n🗑️ Đang dọn dẹp...", parse_mode='Markdown')
            ws.batch_clear(['A2:E1000']) # Xóa dữ liệu cũ
            await update.message.reply_text("✨ Sổ đã sạch sẽ.")
            return

        # --- TÁCH DỮ LIỆU ---
        parts = text.split()
        amount = 0; item = ""; date_str = ""
        
        if len(parts) >= 3 and '/' in parts[0]:
            try: date_str = datetime.strptime(parts[0], "%d/%m").strftime("%d/%m/%Y")
            except: await update.message.reply_text("⛔ Ngày sai (VD: 30/1)"); return
            amount = float(parts[-1])*1000; item = " ".join(parts[1:-1])
        elif len(parts) >= 2 and parts[-1].replace('.', '').isdigit():
            amount = float(parts[-1])*1000; item = " ".join(parts[:-1])
            date_str = datetime.now().strftime("%d/%m/%Y")
        else:
            await update.message.reply_text("⚠️ Sai cú pháp. VD: `Cafe 20`")
            return

        # --- SỬA LỖI BUG "NHẢY CỘT" (QUAN TRỌNG) ---
        # Thay vì dùng append_row (hay bị lỗi nhảy sang cột G), ta tự tính dòng trống ở cột A.
        col_a_values = ws.col_values(1) # Lấy dữ liệu cột A
        next_row = len(col_a_values) + 1 # Dòng tiếp theo là dòng trống
        
        # Ghi đích danh vào ô A{next_row}
        # Lưu ý: Cú pháp update mới yêu cầu range_name và values
        ws.update(
            range_name=f"A{next_row}", 
            values=[[date_str, item, amount]], 
            value_input_option='USER_ENTERED'
        )

        # Fix lỗi mất công thức tính tổng
        total = ws.acell('G1').value
        if (not total or total == '0') and amount > 0:
            ws.update_acell('G1', "=SUM(C:C)")
            total = ws.acell('G1').value

        await update.message.reply_text(
            f"✅ **Lưu:** {item}\n"
            f"💸 Tiền: {amount:,.0f} đ\n"
            f"💰 **TỔNG QUỸ:** {total} VNĐ", 
            parse_mode='Markdown'
        )

    except Exception as e:
        await update.message.reply_text(f"⚠️ Lỗi lưu dữ liệu: {str(e)}")

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