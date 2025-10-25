import asyncio
import logging


def _ensure_private_package() -> None:
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


try:
    from .telegram.client import client
    from .config.settings import settings
    from .cache.updater import update_cache_periodically
    from .telegram.handlers import messages, admin  # noqa: F401  (register handlers)
except ModuleNotFoundError:
    _ensure_private_package()
    from .telegram.client import client
    from .config.settings import settings
    from .cache.updater import update_cache_periodically
    from .telegram.handlers import messages, admin  # noqa: F401  (register handlers)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

async def main():
    # Start the background cache updater
    asyncio.create_task(update_cache_periodically())
    logging.info("Cache updater started.")

    # Connect to Telegram
    await client.start(phone=settings["phone_number"])
    logging.info("Telegram client started.")
    print("Bot is running…")

    # Keep the bot alive
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
