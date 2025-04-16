# config.py

BOT_TOKEN = "7705555230:AAFJsjjLv94kRfJlJMcdGD1BXp3k1x1Dd9A"

DB_CONFIG = {
    "driver": "{ODBC Driver 17 for SQL Server}",
    "server": "WIN-9R9B3VCBI6G\\SEPIDAR",
    "database": "Sepidar01",
    "user": "damavand",
    "password": "damavand",
}
API_CONFIG = {
    "Address": "http://localhost:8585",        # آدرس سرور API
    "GenerationVersion": "1.0",                  # نسخه API مورد استفاده
    "JWT": "Your_JWT_Token_Here",                # توکن JWT (بعد از لاگین یا رجیستر)
    "IntegrationID": "Your_Integration_ID",      # شناسه دستگاه یا IntegrationID
    "ArbitraryCode": "Unique_GUID",             # کد یکتایی که از طرف سیستم دریافت می‌شود
    "EncArbitraryCode": "Encrypted_Code"         # نسخه رمزنگاری شده‌ی کد یکتا
}
