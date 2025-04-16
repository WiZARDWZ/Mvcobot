from telegram import ReplyKeyboardMarkup
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu_reply():
    # منوی ثابت پایین با دکمه تماس با ما
    return ReplyKeyboardMarkup([
        ["🔍 استعلام قطعه", "🛒 سبد خرید"],
        ["🧾 فاکتور", "💰 مانده حساب"],
        ["📱 ثبت نام", "💳 پرداخت آنلاین"],
        ["📞 تماس با ما"]
    ], resize_keyboard=True)

keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("بازگشت به منو اصلی", callback_data="BACK_TO_MAIN_MENU")]
])