"""Inventory processing helpers dedicated to the control-panel statistics views."""
from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional, Tuple

from utils.code_standardization import normalize_code

__all__ = [
    "extract_brand_and_part",
    "replace_partial_code",
    "process_row",
    "process_data",
    "build_part_name_map",
]


def _is_nan(value: Any) -> bool:
    try:
        return bool(value is not None and isinstance(value, float) and math.isnan(value))
    except Exception:
        return False


def extract_brand_and_part(code: Any) -> Tuple[Optional[str], Optional[str]]:
    """Split ``code`` on ``_`` into ``(part_number, brand)`` without trimming."""
    if code is None or code == "":
        return None, None
    if _is_nan(code):
        return None, None

    text = str(code)
    if not text:
        return None, None

    segments = text.split("_")
    part_number = segments[0] if segments else None
    brand = segments[1] if len(segments) > 1 else None
    return part_number, brand


def replace_partial_code(base_code: str, variant: str) -> str:
    """Apply the variant override rules for chained codes."""
    if not base_code or "-" not in base_code:
        return base_code

    prefix, suffix = base_code.rsplit("-", 1)
    variant_text = str(variant)
    if not variant_text:
        return base_code

    if variant_text.isdigit() and len(variant_text) < 5:
        cut = len(variant_text)
        trimmed = suffix[:-cut] if cut <= len(suffix) else ""
        return f"{prefix}-{trimmed}{variant_text}"

    if len(variant_text) == 5:
        return f"{prefix}-{variant_text}"

    return base_code


def _expand_variants(part_number: str) -> List[str]:
    if not part_number:
        return []

    results: List[str] = []
    base_code: Optional[str] = None

    for raw_segment in str(part_number).split("/"):
        segment = str(raw_segment)
        if not segment:
            continue

        if base_code is None:
            if "-" not in segment:
                continue
            suffix = segment.rsplit("-", 1)[-1]
            if len(suffix) >= 5:
                base_code = segment
                results.append(base_code)
            continue

        base_code = replace_partial_code(base_code, segment)
        results.append(base_code)

    if not results and part_number:
        results.append(str(part_number))

    return results


def process_row(row: Dict[str, Any]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []

    part_candidate = row.get("شماره قطعه_ex")
    if not part_candidate:
        part_candidate, _ = extract_brand_and_part(row.get("کد کالا"))
    if not part_candidate:
        part_candidate = row.get("کد کالا")

    brand_candidate = row.get("برند_ex") or row.get("برند")

    variants = _expand_variants(part_candidate) if part_candidate else []
    if not variants and part_candidate:
        variants = [part_candidate]

    seen_codes: set[str] = set()
    for code in variants:
        if not code:
            continue
        code_text = str(code)
        if code_text in seen_codes:
            continue
        seen_codes.add(code_text)
        records.append(
            {
                "برند": brand_candidate,
                "شماره قطعه": code_text,
                "نام کالا": row.get("نام کالا"),
                "فی فروش": row.get("فی فروش"),
                "iran_code": row.get("Iran Code") or row.get("iran_code"),
            }
        )

    if not records:
        fallback_code = row.get("کد کالا")
        if fallback_code:
            code_text = str(fallback_code)
            if code_text not in seen_codes and code_text:
                records.append(
                    {
                        "برند": brand_candidate,
                        "شماره قطعه": code_text,
                        "نام کالا": row.get("نام کالا"),
                        "فی فروش": row.get("فی فروش"),
                        "iran_code": row.get("Iran Code") or row.get("iran_code"),
                    }
                )

    return records


def process_data(raw_data: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    processed: List[Dict[str, Any]] = []
    for row in raw_data:
        base = dict(row)
        part_number, brand = extract_brand_and_part(base.get("کد کالا"))
        base["شماره قطعه_ex"] = part_number
        base["برند_ex"] = brand
        processed.extend(process_row(base))
    return processed


def build_part_name_map(records: Iterable[Dict[str, Any]]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for record in records:
        part_number = record.get("شماره قطعه")
        part_name = record.get("نام کالا")
        if not part_number or not part_name:
            continue
        normalized = normalize_code(part_number).upper()
        if not normalized:
            continue
        if normalized in mapping:
            continue
        mapping[normalized] = str(part_name).strip() or "-"
    return mapping
