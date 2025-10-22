from pathlib import Path

import pandas as pd


def _ensure_private_package() -> None:
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[1].parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


try:
    from privateTelegram.config.settings import APP_DIR, settings
except ModuleNotFoundError:
    _ensure_private_package()
    from privateTelegram.config.settings import APP_DIR, settings

def get_excel_data():
    """
    Reads inventory data from the configured Excel file
    and returns a list of dicts matching the SQL schema.
    Expected columns in Excel:
      - "کد کالا"
      - "توضیحات"   (will map to "Iran Code")
      - "نام کالا"
      - "برند"
      - "قیمت"      (will map to "فی فروش")
    """
    raw_path = settings.get("excel_file") or str(APP_DIR / "inventory.xlsx")
    path = Path(raw_path)
    if not path.is_absolute():
        path = APP_DIR / path

    try:
        df = pd.read_excel(path)
    except Exception as e:
        print(f"❌ خطا در خواندن فایل اکسل '{path}': {e}")
        return []

    expected = ["کد کالا", "توضیحات", "نام کالا", "برند", "قیمت"]
    missing = [c for c in expected if c not in df.columns]
    if missing:
        print(f"❌ فایل اکسل فاقد ستون‌های {missing} است.")
        return []

    records = []
    for _, row in df.iterrows():
        records.append({
            "کد کالا": row["کد کالا"],
            "Iran Code": row["توضیحات"],
            "نام کالا": row["نام کالا"],
            "برند": row["برند"],
            "فی فروش": row["قیمت"]
        })
    return records
