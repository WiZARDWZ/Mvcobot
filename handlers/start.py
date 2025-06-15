from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InputFile
from telegram.ext import ContextTypes
from database.connector_bot import get_setting

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if get_setting("enabled") != "true":
        await update.message.reply_text("⛔️ ربات غیرفعال است. لطفاً بعداً مراجعه کنید.")
        return
    keyboard = [
        [KeyboardButton("🔍 استعلام قطعه")],
        [KeyboardButton("📝 نحوه ثبت سفارش"), KeyboardButton("🚚 نحوه تحویل")],
        [KeyboardButton("📞 تماس با ما")]
    ]
    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=False
    )

    # ارسال عکس خوش‌آمدگویی
    with open("assets/welcome.jpg", "rb") as photo:
        await update.message.reply_photo(
            photo=InputFile(photo),
            caption=(
                "🎉 *خوش آمدید به ربـات هوشمند بازرگانی میروکیلی* \n\n"
                "🚗 تامین و فروش مستقیم قطعات اصلی برندهای *هیوندای* و *کیا*\n"
                "🔍 با چند کلیک ساده، قیمت و موجودی قطعات مورد نیازتان را استعلام بگیرید\n"
                "📦 قطعه اصلی، قیمت به‌روز، پاسخ‌گویی سریع\n\n"
                "از منوی زیر یکی از گزینه‌ها را انتخاب کنید 👇"
            ),
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
