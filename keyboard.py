from telegram import ReplyKeyboardMarkup

def main_menu_reply():
    # منوی ثابت پایین با دکمه تماس با ما
    return ReplyKeyboardMarkup([
        ["🔍 استعلام قطعه", "🛒 سبد خرید"],
        ["🧾 فاکتور", "💰 مانده حساب"],
        ["📱 ثبت نام", "💳 پرداخت آنلاین"],
        ["📞 تماس با ما"]
    ], resize_keyboard=True)
