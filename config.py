# config.py

BOT_TOKEN = "7705555230:AAFJsjjLv94kRfJlJMcdGD1BXp3k1x1Dd9A"

DB_CONFIG = {
    "driver": "{ODBC Driver 17 for SQL Server}",
    "server": "WIN-9R9B3VCBI6G\\SEPIDAR",
    "database": "Sepidar01",
    "user": "damavand",
    "password": "damavand",
}

# ===== اینجا دقیقاً باید به شکل زیر باشه (نکته: کاما بعد از هر خط!) =====
BOT_DB_CONFIG = {
    "driver": "{ODBC Driver 17 for SQL Server}",  # کاما مهم است
    "server": "AMIN\\MVCO",                        # کاما مهم است
    "database": "MvcobotDB",                       # کاما مهم است
    "trusted_connection": "yes"                    # آخر خط بدون کاما
}

BASE_URL = 'http://localhost:8585'
API_VERSION = '1.0.0'
REGISTRATION_CODE = '10054425'
USERNAME = 'mvcobot'
PASSWORD = '001212'
