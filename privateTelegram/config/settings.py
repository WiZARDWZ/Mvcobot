import json
import shutil
import sys
from pathlib import Path
from typing import Any


def _package_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _bundle_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidate = Path(sys._MEIPASS) / "privateTelegram"
        if candidate.exists():
            return candidate
    return _package_root()


PACKAGE_ROOT = _package_root()
BUNDLE_ROOT = _bundle_root()


# Determine where to load/save runtime assets:
# - If frozen by PyInstaller, look next to the executable (sys.argv[0])
# - Otherwise, in the project root (two levels up from this file)
if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.argv[0]).parent
else:
    APP_DIR = PACKAGE_ROOT


def _ensure_runtime_artifact(filename: str) -> Path:
    target = APP_DIR / filename
    if target.exists():
        return target

    source = BUNDLE_ROOT / filename
    if source.exists():
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        except Exception as exc:  # pragma: no cover - best-effort seeding
            print(f"⚠️ Unable to seed '{filename}' into runtime directory: {exc}")
    return target


# Ensure runtime copies of the bundled assets exist when frozen.
for artifact in (
    "bot_settings.json",
    "inventory.xlsx",
    "session.session",
    "private_metrics.json",
):
    _ensure_runtime_artifact(artifact)


SETTINGS_FILE = APP_DIR / "bot_settings.json"

# In-memory settings dict
settings: dict[str, Any] = {}


def load_settings() -> None:
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            settings.update(json.load(f))
    except FileNotFoundError:
        # Seed defaults from the bundled template if the file is missing
        default_path = BUNDLE_ROOT / "bot_settings.json"
        if default_path.exists():
            try:
                with open(default_path, "r", encoding="utf-8") as template:
                    settings.update(json.load(template))
            except Exception as exc:
                print(f"⚠️ Failed to load default bot_settings.json: {exc}")
        save_settings()


def save_settings() -> None:
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def _setdefault(key: str, value: Any) -> bool:
    if key not in settings:
        settings[key] = value
        return True
    return False


def _ensure_excel_path() -> bool:
    raw = settings.get("excel_file")
    if not raw:
        settings["excel_file"] = str(APP_DIR / "inventory.xlsx")
        return True

    path = Path(str(raw))
    if not path.is_absolute():
        settings["excel_file"] = str(APP_DIR / path)
        return True
    return False


# Initialize settings on import
load_settings()

# ─── Default values ───
dirty = False

# Data source: "sql" or "excel"
dirty |= _setdefault("data_source", "sql")

# Toggle for private message auto-replies
dirty |= _setdefault("dm_enabled", True)

# Working hours & delivery defaults mirror the shipped JSON
dirty |= _setdefault("cache_duration_minutes", 20)
dirty |= _setdefault("changeover_hour", "15:00")

dirty |= _setdefault("working_hours", {"start": "08:00", "end": "17:30"})
dirty |= _setdefault("thursday_hours", {"start": "08:00", "end": "13:30"})
dirty |= _setdefault("disable_friday", True)
dirty |= _setdefault("lunch_break", {"start": "14:40", "end": "15:00"})
dirty |= _setdefault("delivery_info", {
    "before_15": "🚚 تحویل کالا هر روز ساعت 16 و پنجشنبه ها ساعت 12:30 در دفتر بازار \n🛵 ارسال مستقیم از انبار با زمان تقریبی تحویل 60 دقیقه در هر ساعتی امکان پذیر می باشد (هزینه پیک دارد)",
    "after_15": "🛵 ارسال مستقیم از انبار با زمان تقریبی تحویل 60 دقیقه در هر ساعتی امکان پذیر می باشد (هزینه پیک دارد)",
})

dirty |= _ensure_excel_path()

if dirty:
    save_settings()
