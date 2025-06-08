# interfaces/telegram/bot.py
import logging
import asyncio
from telegram.ext import Application
from .handlers import register_handlers
from config import settings

logger = logging.getLogger(__name__)

async def run_bot():
    """Run the bot with proper event loop handling"""
    try:
        application = Application.builder().token(settings.telegram_token).build()
        register_handlers(application)
        logger.info("Telegram bot starting...")
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        logger.info("Bot is now running")
        while True:
            await asyncio.sleep(3600)  # Keep the bot running
    except Exception as e:
        logger.error("Telegram bot error: %s", str(e))
    finally:
        if 'application' in locals():
            await application.stop()
            await application.shutdown()

def start_bot():
    """Start the bot in a new event loop"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_bot())
    loop.close()