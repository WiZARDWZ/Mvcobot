from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton

def main_menu_reply():
    """
    منوی اصلی (۳ ردیف دقیقاً مطابق خواسته)
    """
    return ReplyKeyboardMarkup(
        [
            ["🔍 استعلام قطعه"],
            ["📝 نحوه ثبت سفارش", "🚚 نحوه تحویل"],
            ["📞 تماس با ما"]
        ],
        resize_keyboard=True
    )

def back_to_main_inline():
    """
    دکمه‌ی اینلاین برای بازگشت به منوی اصلی.
    """
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="main_menu")]
    ])
