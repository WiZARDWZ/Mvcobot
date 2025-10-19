"""One-off migration script to move bot_settings.json into the database."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Dict

from database.connector_bot import get_connection
from .models import ensure_schema

LOGGER = logging.getLogger(__name__)


def _load_json(path: Path) -> Dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("bot_settings.json must contain a JSON object")
    return {str(k): str(v) for k, v in data.items()}


def migrate(json_path: Path, *, force: bool = False) -> None:
    ensure_schema(get_connection)
    payload = _load_json(json_path)

    with get_connection() as conn:
        cur = conn.cursor()
        for key, value in payload.items():
            if not force:
                row = cur.execute(
                    "SELECT 1 FROM bot_settings WHERE [key] = ?", key
                ).fetchone()
                if row:
                    LOGGER.info("Skip existing key %s (use --force to overwrite)", key)
                    continue
            cur.execute(
                """
                MERGE bot_settings AS target
                USING (SELECT ? AS [key]) AS src
                    ON target.[key] = src.[key]
                WHEN MATCHED THEN
                    UPDATE SET [value] = ?, updated_at = SYSUTCDATETIME()
                WHEN NOT MATCHED THEN
                    INSERT ([key], [value], updated_at)
                    VALUES (?, ?, SYSUTCDATETIME());
                """,
                key,
                str(value),
                key,
                str(value),
            )
        conn.commit()
    LOGGER.info("Migration completed for %s", json_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Path to bot_settings.json")
    parser.add_argument("--force", action="store_true", help="Overwrite existing keys")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    migrate(args.path, force=args.force)


if __name__ == "__main__":
    main()
