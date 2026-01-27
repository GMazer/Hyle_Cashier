import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

TOKEN = '8374820897:AAGLUxuxF5XqlZgHA4O6X8rmMWsJWo4sGqE' # Điền token của bạn vào đây

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data['total'] = 0
    context.user_data['history'] = []
    
    await update.message.reply_text(
        "Bot quản lý chi tiêu đã sẵn sàng!\n\n"
        "📝 **Cú pháp nhập liệu:**\n"
        "- `30/1 ngô 10` => Ngày 30/1 mua Ngô giá 10k\n"
        "- `10` => Hôm nay mua 'Khác' giá 10k\n\n"
        "✅ Nhập `done` để chốt sổ và reset.\n"
        "📜 Nhập `/ls` để xem danh sách.",
        parse_mode='Markdown'
    )

async def ls_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    history = context.user_data.get('history', [])
    total = context.user_data.get('total', 0)
    
    if not history:
        await update.message.reply_text("📭 Danh sách trống.")
        return

    # Tạo bảng tin nhắn đẹp mắt hơn
    msg = "🧾 **DANH SÁCH CHI TIÊU**\n"
    msg += "-" * 25 + "\n"
    
    for item in history:
        # item['date'] đã là string dạng dd/mm
        msg += f"📅 {item['date']} | {item['name']} : {item['amount']:,.0f}\n"
    
    msg += "-" * 25 + "\n"
    msg += f"💰 **TỔNG CỘNG:** {total:,.0f} vnđ"

    await update.message.reply_text(msg)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_data = context.user_data

    # Khởi tạo nếu chưa có
    if 'total' not in user_data:
        user_data['total'] = 0
        user_data['history'] = []

    # --- 1. Xử lý lệnh DONE ---
    if text.lower() == 'done':
        final_total = user_data['total']
        if final_total == 0:
             await update.message.reply_text("Chưa có gì để thanh toán.")
        else:
            await update.message.reply_text(
                f"✅ **Đã chốt sổ thành công!**\nTổng thanh toán: {final_total:,.0f} vnđ.\nDữ liệu đã được reset.",
                parse_mode='Markdown'
            )
            user_data['total'] = 0
            user_data['history'] = []
        return

    # --- 2. Xử lý logic tách chuỗi (Parsing) ---
    try:
        parts = text.split() # Tách chuỗi bằng khoảng trắng
        
        amount = 0
        item_name = ""
        date_str = ""
        
        # TRƯỜNG HỢP 1: Nhập đúng chuẩn "30/1 ngô 10"
        # Điều kiện: Có ít nhất 3 phần tử VÀ phần tử đầu tiên chứa dấu "/"
        if len(parts) >= 3 and '/' in parts[0]:
            # Xử lý ngày
            day_month = parts[0]
            # Kiểm tra xem ngày có hợp lệ không
            try:
                valid_date = datetime.strptime(day_month, "%d/%m")
                date_str = valid_date.strftime("%d/%m") # Format lại cho đẹp
            except ValueError:
                # Nếu nhập 30/1 mà sai định dạng
                await update.message.reply_text("⛔ Định dạng ngày sai. Hãy nhập dạng 30/1 hoặc 30/01")
                return

            # Xử lý giá tiền (lấy phần tử cuối cùng)
            amount = float(parts[-1]) * 1000
            
            # Xử lý tên món (lấy tất cả ở giữa)
            item_name = " ".join(parts[1:-1])

        # TRƯỜNG HỢP 2: Chỉ nhập số "10" (Giữ tính năng cũ cho nhanh)
        elif len(parts) == 1 and parts[0].replace('.', '').isdigit():
            amount = float(parts[0]) * 1000
            item_name = "Khác"
            date_str = datetime.now().strftime("%d/%m") # Lấy ngày hôm nay
            
        else:
            raise ValueError("Sai cú pháp")

        # --- 3. Lưu dữ liệu ---
        user_data['total'] += amount
        user_data['history'].append({
            'date': date_str,
            'name': item_name,
            'amount': amount
        })

        await update.message.reply_text(
            f"✅ Đã thêm: **{item_name}** ({date_str})\n"
            f"💸 Giá: {amount:,.0f} vnđ\n"
            f"💰 **Tổng tạm tính:** {user_data['total']:,.0f} vnđ",
            parse_mode='Markdown'
        )

    except ValueError:
        await update.message.reply_text(
            "⚠️ **Lỗi cú pháp!**\n"
            "Vui lòng nhập theo mẫu:\n"
            "`30/1 ngô 10` (Ngày món tiền)\n"
            "hoặc `done` để kết thúc.",
            parse_mode='Markdown'
        )

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('ls', ls_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot v2 đang chạy...")
    application.run_polling()