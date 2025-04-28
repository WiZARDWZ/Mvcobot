# config.py

BOT_TOKEN = "7570544705:AAGc-DPFEOpW08HIGjsFR8MdykNrlbaU5-4"

DB_CONFIG = {
    "driver": "{ODBC Driver 17 for SQL Server}",
    "server": "WIN-9R9B3VCBI6G\\SEPIDAR",
    "database": "Sepidar01",
    "user": "damavand",
    "password": "damavand",
}

# ===== اینجا دقیقاً باید به شکل زیر باشه (نکته: کاما بعد از هر خط!) =====
# BOT_DB_CONFIG = {
#     "driver": "{ODBC Driver 17 for SQL Server}",
#     "server": "AMIN\\MVCO",
#     "database": "MvcobotDB",
#     "trusted_connection": "yes"
# }
BOT_DB_CONFIG = {
    "driver": "{ODBC Driver 17 for SQL Server}",
    "server": "WIN-9R9B3VCBI6G\\SEPIDAR",
    "database": "MvcobotDB",
    "user": "damavand",
    "password": "damavand",
}
BASE_URL = 'http://localhost:8585'
API_VERSION = '1.0.0'
REGISTRATION_CODE = '10054425'
USERNAME = 'mvcobot'
PASSWORD = '001212'
