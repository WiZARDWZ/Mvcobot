# processor/transformer.py

import pandas as pd
from privateTelegram.processor.extractor import extract_brand_and_part, replace_partial_code

def process_row(row):
    records = []

    # Prefer the part/brand extracted from code if available
    part_extracted, brand_extracted = row.get("شماره قطعه_ex"), row.get("برند_ex")
    if pd.notna(part_extracted):
        part_number = part_extracted
    else:
        part_number, _ = extract_brand_and_part(row.get("کد کالا", ""))
    if not part_number:
        part_number = row.get("کد کالا", "")

    # Decide which brand to use
    raw_brand = row.get("برند")
    if pd.notna(brand_extracted) and brand_extracted:
        brand = brand_extracted
    else:
        brand = raw_brand or "نامشخص"

    last_base_code = None
    for segment in str(part_number).split("/"):
        seg = segment.strip()
        if "-" in seg and len(seg.split("-")[-1]) >= 5:
            last_base_code = seg
        elif last_base_code:
            last_base_code = replace_partial_code(last_base_code, seg)
        else:
            continue

        records.append({
            "برند": brand,
            "شماره قطعه": last_base_code,
            "نام کالا": row.get("نام کالا", ""),
            "فی فروش": row.get("فی فروش", 0),
            "iran_code": row.get("Iran Code")
        })

    return records

def process_data(raw_data):
    processed_records = []
    df = pd.DataFrame(raw_data)

    # Apply extraction only if there's a "کد کالا" column
    if "کد کالا" in df.columns:
        extras = df["کد کالا"].apply(lambda x: pd.Series(extract_brand_and_part(x)))
        extras.columns = ["شماره قطعه_ex", "برند_ex"]
        df = pd.concat([df, extras], axis=1)

    for _, row in df.iterrows():
        processed_records.extend(process_row(row))

    return processed_records
