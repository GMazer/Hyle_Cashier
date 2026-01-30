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

def get_google_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    json_creds = os.environ.get("GOOGLE_CREDENTIALS")
    
    try:
        if json_creds:
            # Sửa lỗi format JSON nếu có ký tự lạ
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.full_name
    sheet_id = context.user_data.get('sheet_id')
    
    if sheet_id:
        await update.message.reply_text(f"✅ Bot đang kết nối với sổ của {user_name}.\nGõ `/ls` để xem, hoặc gửi Link mới để đổi sổ.", parse_mode='Markdown')
    else:
        await update.message.reply_text(
            f"👋 Chào {user_name}!\n\n"
            f"Mọi cấu hình đã OK. Giờ bạn chỉ cần gửi **Link Google Sheet** vào đây là xong.\n"
            f"(Nhớ chắc chắn đã Share Editor cho: `{BOT_EMAIL}`)",
            parse_mode='Markdown'
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🆘 **HƯỚNG DẪN**\n- Nhập tiền: `30/1 Cafe 20`\n- Xem lại: `/ls`\n- Gửi Link Sheet để kết nối lại.",
        parse_mode='Markdown'
    )

async def ls_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sheet_id = context.user_data.get('sheet_id')
    if not sheet_id:
        await update.message.reply_text("⚠️ Chưa có sổ. Gửi Link Sheet trước đã!")
        return

    try:
        gc = get_google_client()
        # Dùng open_by_key cho nhanh
        ws = gc.open_by_key(sheet_id).sheet1
        vals = ws.get_all_values()
        
        if len(vals) < 2:
            await update.message.reply_text("📭 Sổ trống trơn.")
            return

        last_10 = vals[1:][-10:]
        msg = "🧾 **10 KHOẢN GẦN NHẤT:**\n" + "-"*20 + "\n"
        for r in last_10:
            d = r[0] if len(r)>0 else ""
            n = r[1] if len(r)>1 else ""
            m = r[2] if len(r)>2 else "0"
            msg += f"{d} | {n} : {m}\n"
            
        total = ws.acell('G1').value or "0"
        msg += "-"*20 + f"\n💰 **TỔNG: {total}**"
        await update.message.reply_text(msg, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(f"⚠️ Lỗi đọc sổ: {str(e)}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    sheet_id = context.user_data.get('sheet_id')

    # --- 1. LOGIC NHẬN LINK (MỚI - MẠNH MẼ HƠN) ---
    if "docs.google.com/spreadsheets" in text:
        await update.message.reply_text("⏳ Đang thử kết nối...")
        try:
            gc = get_google_client()
            if not gc:
                await update.message.reply_text("❌ Lỗi: Không đọc được Key JSON trên Render!")
                return

            # THAY ĐỔI LỚN: Dùng open_by_url thay vì regex ID
            # Cách này chấp nhận mọi thể loại link (có gid, có edit, v.v...)
            sh = gc.open_by_url(text) 
            ws = sh.sheet1
            
            # Setup cơ bản
            if not ws.acell('A1').value:
                 ws.update('A1:D1', [["Ngày", "Món", "Tiền", "Ghi chú"]])
                 ws.update('F1', "TỔNG:")
                 ws.update('G1', "=SUM(C:C)")

            context.user_data['sheet_id'] = sh.id
            context.user_data['sheet_url'] = text
            
            await update.message.reply_text(
                f"🎉 **THÀNH CÔNG RỒI!**\n"
                f"Đã kết nối sổ: **{sh.title}**\n"
                f"Giờ nhập thử món nào đó đi: `Test 1`", 
                parse_mode='Markdown'
            )
        except Exception as e:
            # IN RA LỖI CỤ THỂ ĐỂ DEBUG
            error_msg = str(e)
            if "403" in error_msg:
                await update.message.reply_text(f"⛔ **Lỗi 403 (Quyền):** Bot vẫn bị chặn. Hãy thử bỏ Share rồi Share lại xem sao.\nLỗi chi tiết: {error_msg}")
            elif "404" in error_msg:
                await update.message.reply_text(f"⛔ **Lỗi 404 (Không tìm thấy):** Link sai hoặc File đã bị xóa.\nLỗi chi tiết: {error_msg}")
            else:
                await update.message.reply_text(f"☠️ **Lỗi lạ:** {error_msg}")
        return

    # --- 2. LOGIC NHẬP TIỀN ---
    if not sheet_id:
        await update.message.reply_text("⚠️ Gửi Link Google Sheet vào đây trước nhé.")
        return

    try:
        gc = get_google_client()
        ws = gc.open_by_key(sheet_id).sheet1
        
        if text.lower() in ['done', 'chốt']:
            ws.batch_clear(['A2:E1000'])
            await update.message.reply_text("✨ Đã xóa dữ liệu cũ.")
            return

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

        ws.append_row([date_str, item, amount], value_input_option='USER_ENTERED')
        
        # Tự fix lỗi tổng = 0
        total = ws.acell('G1').value
        if (not total or total == '0') and amount > 0:
            ws.update('G1', "=SUM(C:C)")
            total = ws.acell('G1').value

        await update.message.reply_text(f"✅ Lưu: **{item}** ({amount:,.0f})\n💰 Tổng: **{total}**", parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text(f"⚠️ Lỗi khi lưu: {str(e)}")

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