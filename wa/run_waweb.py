# wa/run_waweb.py — Runner (دیباگ فعال)
import asyncio
import os
from typing import List, Dict, Any
from wa.waweb import WAConfig, WAWebBot
from wa.bridge import replies_for_codes

async def on_codes(codes: List[str], chat_meta: Dict[str, Any]) -> List[str]:
    return await replies_for_codes(codes)

async def on_non_code(messages: List[str], chat_meta: Dict[str, Any]) -> None:
    pass

async def main():
    cfg = WAConfig(
        user_data_dir=os.environ.get("WA_USER_DATA_DIR", "./.wa-user-data"),
        headless=os.environ.get("HEADLESS", "false").lower() == "true",
        slow_mo_ms=int(os.environ.get("SLOW_MO_MS", "110")),
        idle_scan_interval_sec=float(os.environ.get("SCAN_INTERVAL", "10")),
        debug_send_dot_if_no_reply=True,
        debug_tag=os.environ.get("WA_DEBUG_TAG", "WADEBUG"),
    )
    bot = WAWebBot(cfg, on_codes=on_codes, on_non_code=on_non_code)
    await bot.start()
    await bot.run_forever()

if __name__ == "__main__":
    asyncio.run(main())
