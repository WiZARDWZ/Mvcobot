from telegram import Update
from telegram.ext import ConversationHandler, CommandHandler, MessageHandler, filters, CallbackContext
import requests
from config import API_CONFIG  # شامل URL و سایر تنظیمات مورد نیاز
from database.connector import get_customer_by_phone
from utils.formatter import format_invoices_message

# تعریف حالت‌ها
ASK_PHONE = 1

def my_invoice_command(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("لطفاً شماره تلفن همراه خود را وارد کنید:")
    return ASK_PHONE

def receive_phone(update: Update, context: CallbackContext) -> int:
    phone_number = update.message.text.strip()
    # اعتبارسنجی شماره تلفن ساده (مثلاً بررسی حروف غیرمجاز یا طول)
    if not phone_number.isdigit() or len(phone_number) < 10:
        update.message.reply_text("لطفاً یک شماره تلفن معتبر وارد کنید:")
        return ASK_PHONE

    # جستجوی مشتری در پایگاه داده با استفاده از شماره تلفن
    customer = get_customer_by_phone(phone_number)
    if not customer:
        update.message.reply_text("مشتری با این شماره تلفن یافت نشد.")
        return ConversationHandler.END

    # دریافت کد مشتری
    customer_code = customer.get("code")

    # درخواست فاکتورهای من از API سپیدار
    invoices = get_invoices_by_customer(customer_code)
    if not invoices:
        update.message.reply_text("هیچ فاکتوری برای شما یافت نشد.")
    else:
        formatted_message = format_invoices_message(invoices)
        update.message.reply_text(formatted_message, parse_mode="HTML")
    return ConversationHandler.END

def get_invoices_by_customer(customer_code: str) -> list:
    # در اینجا یک درخواست HTTP به API سپیدار انجام می‌شود
    headers = {
        "GenerationVersion": API_CONFIG["GenerationVersion"],
        "Authorization": API_CONFIG["JWT"],
        "IntegrationID": API_CONFIG["IntegrationID"],
        "ArbitraryCode": API_CONFIG["ArbitraryCode"],
        "EncArbitraryCode": API_CONFIG["EncArbitraryCode"],
    }
    # در این نمونه فرض می‌کنیم که فیلتر مشتری با پارامتر query به API ارسال می‌شود (یا API بر اساس IntegrationID و اطلاعات مشتری فیلتر می‌کند)
    url = f"{API_CONFIG['Address']}/api/invoices/?customerCode={customer_code}"
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        # فرض می‌کنیم data لیستی از فاکتورها برمی‌گرداند
        return data
    except Exception as ex:
        # ثبت خطا و ارسال پیام مناسب در صورت بروز مشکل
        print(f"Error getting invoices: {ex}")
        return []

def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("عملیات لغو شد.")
    return ConversationHandler.END

def setup_invoice_handlers(dispatcher):
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("myinvoice", my_invoice_command)],
        states={
            ASK_PHONE: [MessageHandler(filters.text & ~filters.command, receive_phone)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    dispatcher.add_handler(conv_handler)
