def _ensure_private_package() -> None:
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


try:
    from privateTelegram.cache.updater import get_cached_data
    from privateTelegram.utils.formatting import normalize_code
except ModuleNotFoundError:
    _ensure_private_package()
    from privateTelegram.cache.updater import get_cached_data
    from privateTelegram.utils.formatting import normalize_code

ORIGINAL_BRANDS = ["MOBIS", "GENUINE"]

def find_similar_products(partial_code, only_original=False):
    data = get_cached_data()
    target = normalize_code(partial_code)
    results = {}

    for row in data:
        code = normalize_code(str(row.get("شماره قطعه", "")))
        brand = row.get("برند", "نامشخص")
        price = row.get("فی فروش", 0)
        if isinstance(price, str) and price.isdigit():
            price = int(price)

        if code == target:
            if only_original and brand not in ORIGINAL_BRANDS:
                continue
            if brand not in results or price > results[brand]["price"]:
                results[brand] = {
                    "product_code": row["شماره قطعه"],
                    "brand": brand,
                    "price": price,
                    "name": row.get("نام کالا", ""),
                    # now pulling from the transformer
                    "iran_code": row.get("iran_code")
                }
    return list(results.values())

def find_partial_matches(partial_code):
    data = get_cached_data()
    key = normalize_code(partial_code)
    matches = []
    for row in data:
        code = normalize_code(str(row.get("شماره قطعه", "")))
        if code.startswith(key):
            matches.append({
                "product_code": row["شماره قطعه"],
                "brand": row.get("برند", "نامشخص"),
                "price": row.get("فی فروش", 0),
                "name": row.get("نام کالا", ""),
                "iran_code": row.get("iran_code")
            })
    return matches
