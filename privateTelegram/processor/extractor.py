import pandas as pd

def extract_brand_and_part(code):
    if pd.isna(code):
        return None, None
    parts = str(code).split("_")
    part_number = parts[0]
    brand = parts[1] if len(parts) > 1 else None
    return part_number, brand

def replace_partial_code(base_code, variant):
    try:
        prefix, suffix = base_code.rsplit("-", 1)
    except ValueError:
        return base_code
    if variant.isdigit() and len(variant) < 5:
        new_suffix = suffix[:-len(variant)] + variant
        return f"{prefix}-{new_suffix}"
    if len(variant) == 5:
        return f"{prefix}-{variant}"
    return base_code
