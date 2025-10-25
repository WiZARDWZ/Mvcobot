# processor/transformer.py

from typing import List, Optional, Set

import pandas as pd


def _ensure_private_package() -> None:
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


try:
    from privateTelegram.processor.extractor import (
        extract_brand_and_part,
        replace_partial_code,
    )
except ModuleNotFoundError:
    _ensure_private_package()
    from privateTelegram.processor.extractor import (
        extract_brand_and_part,
        replace_partial_code,
    )


def _select_part_number(row: pd.Series) -> str:
    part_extracted = row.get("شماره قطعه_ex")
    if pd.notna(part_extracted):
        return str(part_extracted)

    part_number, _ = extract_brand_and_part(row.get("کد کالا", ""))
    if part_number is not None:
        return str(part_number)

    fallback = row.get("کد کالا", "")
    return "" if pd.isna(fallback) else str(fallback)


def _select_brand(row: pd.Series) -> Optional[str]:
    brand_extracted = row.get("برند_ex")
    if pd.notna(brand_extracted) and brand_extracted not in ("", None):
        return brand_extracted

    raw_brand = row.get("برند")
    if pd.notna(raw_brand) and raw_brand not in ("", None):
        return raw_brand

    return None


def _expand_part_variants(part_number: str) -> List[str]:
    if not part_number:
        return []

    segments = str(part_number).split("/")
    if len(segments) == 1:
        return [segments[0]] if segments[0] else []

    results: List[str] = []
    last_code: Optional[str] = None

    for raw_segment in segments:
        segment = str(raw_segment).strip()
        if not segment:
            continue

        if last_code is None:
            if "-" not in segment:
                continue
            suffix = segment.rsplit("-", 1)[-1]
            if len(suffix) < 5:
                continue
            last_code = segment
            results.append(last_code)
            continue

        last_code = replace_partial_code(last_code, segment)
        results.append(last_code)

    if not results and segments:
        base = str(part_number)
        if base:
            results.append(base)

    return results


def process_row(row):
    records = []

    part_number = _select_part_number(row)
    brand = _select_brand(row)
    iran_code = row.get("Iran Code") if "Iran Code" in row else row.get("iran_code")

    variants = _expand_part_variants(part_number)
    if not variants and part_number:
        variants = [part_number]

    seen: Set[str] = set()
    for code in variants:
        if not code or code in seen:
            continue
        seen.add(code)
        records.append(
            {
                "برند": brand,
                "شماره قطعه": code,
                "نام کالا": row.get("نام کالا", ""),
                "فی فروش": row.get("فی فروش", 0),
                "iran_code": iran_code,
            }
        )

    return records


def process_data(raw_data):
    processed_records = []
    df = pd.DataFrame(raw_data)

    if "کد کالا" in df.columns:
        extras = df["کد کالا"].apply(lambda value: pd.Series(extract_brand_and_part(value)))
        extras.columns = ["شماره قطعه_ex", "برند_ex"]
        df = pd.concat([df, extras], axis=1)

    for _, row in df.iterrows():
        processed_records.extend(process_row(row))

    return processed_records
