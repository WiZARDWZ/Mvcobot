import asyncio
import logging

from privateTelegram.telegram.client import client
from privateTelegram.config.settings import settings
from privateTelegram.cache.updater import update_cache_periodically

# Register handlers so decorators take effect
from privateTelegram.telegram.handlers import messages, admin

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
