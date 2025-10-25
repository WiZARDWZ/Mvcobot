import pandas as pd


def extract_brand_and_part(code):
    """Return the raw part number and brand extracted from ``code``."""

    if pd.isna(code):
        return None, None

    text = str(code)
    parts = text.split("_", 1)
    part_number = parts[0] if parts else None
    brand = parts[1] if len(parts) > 1 else None
    return part_number, brand


def replace_partial_code(base_code, variant):
    """Rebuild ``base_code`` by applying a ``variant`` chunk."""

    base_text = str(base_code)
    variant_text = str(variant)

    try:
        prefix, suffix = base_text.rsplit("-", 1)
    except ValueError:
        return base_text

    if variant_text.isdigit() and len(variant_text) < 5:
        trim = min(len(suffix), len(variant_text))
        new_suffix = suffix[:-trim] + variant_text
        return f"{prefix}-{new_suffix}"

    if len(variant_text) == 5:
        return f"{prefix}-{variant_text}"

    return base_text
