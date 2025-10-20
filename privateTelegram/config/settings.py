import json
import sys
from pathlib import Path

# Determine where to load/save bot_settings.json:
# - If frozen by PyInstaller, look next to the executable (sys.argv[0])
# - Otherwise, in the project root (two levels up from this file)
if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.argv[0]).parent
else:
    APP_DIR = Path(__file__).parent.parent
SETTINGS_FILE = APP_DIR / "bot_settings.json"

# In-memory settings dict
settings = {}

def load_settings():
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            settings.update(json.load(f))
    except FileNotFoundError:
        # Create the file with defaults if it doesn't exist
        save_settings()

def save_settings():
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

# Initialize settings on import
load_settings()

# ─── Default values ───
# Data source: "sql" or "excel"
settings.setdefault("data_source", "sql")
# If using Excel, this is the filename or path (relative to APP_DIR or absolute)
settings.setdefault("excel_file", "inventory.xlsx")

# Enable/Disable private message auto-replies
settings.setdefault("enabled", True)
settings.setdefault("dm_enabled", True)
settings.setdefault("cache_duration_minutes", 20)
settings.setdefault("working_hours", {"start": "08:00", "end": "17:30"})
settings.setdefault("thursday_hours", {"start": "08:00", "end": "13:30"})
settings.setdefault("disable_friday", True)
settings.setdefault("lunch_break", {"start": "14:30", "end": "15:00"})
settings.setdefault("delivery_info", {"before_15": "", "after_15": ""})
settings.setdefault("changeover_hour", "15:00")
settings.setdefault("admin_group_ids", [])
settings.setdefault("secondary_group_ids", [])
