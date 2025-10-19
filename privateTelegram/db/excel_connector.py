import pandas as pd
from config.settings import settings

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
    path = settings.get("excel_file")
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
