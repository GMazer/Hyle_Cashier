import logging
import os
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# --- CẤU HÌNH ---
# Token của bạn (Đã điền sẵn)
TOKEN = '8374820897:AAGLUxuxF5XqlZgHA4O6X8rmMWsJWo4sGqE' 

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['total'] = 0
    context.user_data['history'] = []
    
    await update.message.reply_text(
        "Bot quản lý chi tiêu (Render Version) sẵn sàng!\n\n"
        "📝 **Cú pháp:**\n"
        "- `30/1 ngô 10` => Ngày 30/1 mua Ngô 10k\n"
        "- `10` => Hôm nay mua 'Khác' 10k\n"
        "✅ `done` để chốt sổ.\n"
        "📜 `/ls` xem danh sách.",
        parse_mode='Markdown'
    )

async def ls_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    history = context.user_data.get('history', [])
    total = context.user_data.get('total', 0)
    
    if not history:
        await update.message.reply_text("📭 Danh sách trống.")
        return

    msg = "🧾 **DANH SÁCH CHI TIÊU**\n" + "-" * 25 + "\n"
    for item in history:
        msg += f"📅 {item['date']} | {item['name']} : {item['amount']:,.0f}\n"
    msg += "-" * 25 + "\n" + f"💰 **TỔNG:** {total:,.0f} vnđ"

    await update.message.reply_text(msg)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_data = context.user_data

    if 'total' not in user_data:
        user_data['total'] = 0
        user_data['history'] = []

    if text.lower() == 'done':
        final_total = user_data['total']
        if final_total == 0:
             await update.message.reply_text("Chưa có gì để thanh toán.")
        else:
            await update.message.reply_text(
                f"✅ **Đã chốt sổ!** Tổng: {final_total:,.0f} vnđ.\nReset dữ liệu.",
                parse_mode='Markdown'
            )
            user_data['total'] = 0
            user_data['history'] = []
        return

    try:
        parts = text.split()
        amount = 0
        item_name = ""
        date_str = ""
        
        if len(parts) >= 3 and '/' in parts[0]:
            try:
                date_str = datetime.strptime(parts[0], "%d/%m").strftime("%d/%m")
            except ValueError:
                await update.message.reply_text("⛔ Sai ngày. Nhập dạng 30/1")
                return
            amount = float(parts[-1]) * 1000
            item_name = " ".join(parts[1:-1])

        elif len(parts) == 1 and parts[0].replace('.', '').isdigit():
            amount = float(parts[0]) * 1000
            item_name = "Khác"
            date_str = datetime.now().strftime("%d/%m")
            
        else:
            raise ValueError("Sai cú pháp")

        user_data['total'] += amount
        user_data['history'].append({'date': date_str, 'name': item_name, 'amount': amount})

        await update.message.reply_text(
            f"✅ Thêm: **{item_name}** ({date_str}) - {amount:,.0f} vnđ\n"
            f"💰 **Tổng:** {user_data['total']:,.0f} vnđ",
            parse_mode='Markdown'
        )

    except ValueError:
        await update.message.reply_text("⚠️ Sai cú pháp! Nhập `30/1 ngô 10` hoặc `10`.")

if __name__ == '__main__':
    # --- PHẦN TỰ ĐỘNG NHẬN DIỆN MÔI TRƯỜNG ---
    # Render sẽ tự động cung cấp biến RENDER_EXTERNAL_URL và PORT
    WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL") 
    PORT = int(os.environ.get("PORT", "8443"))

    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('ls', ls_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Tự động chọn chế độ chạy
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
