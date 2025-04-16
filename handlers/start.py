from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InputFile
from telegram.ext import ContextTypes

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("🔍 استعلام قطعه")],
        [KeyboardButton("🧾 فاکتور"), KeyboardButton("💳 پرداخت")],
        [KeyboardButton("🛒 سبد خرید"), KeyboardButton("📊 موجودی حساب")],
        [KeyboardButton("📝 ثبت‌نام")],
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
            caption="🎉 به *سیستم فروش هوشمند بازرگانی میروکیلی* خوش آمدید 🎉\n\nاز منوی زیر یکی از گزینه‌ها را انتخاب کنید:",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
