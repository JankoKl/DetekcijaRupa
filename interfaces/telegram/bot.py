# interfaces/telegram/bot.py
"""
Telegram bot interface for pothole notifications.
"""
import logging
import asyncio
import threading
from typing import Optional, Dict, Any
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from config.config import TelegramConfig
from config.logging import get_logger


class TelegramBot:
    """Telegram bot for sending pothole notifications."""

    def __init__(self, config: TelegramConfig):
        self.config = config
        self.logger = get_logger(__name__)
        self.application: Optional[Application] = None
        self.running = False
        self._bot_thread: Optional[threading.Thread] = None

        if not self.config.token:
            raise ValueError("Telegram bot token is required")

        self._initialize_bot()

    def _initialize_bot(self):
        """Initialize the Telegram bot application."""
        try:
            self.application = Application.builder().token(self.config.token).build()

            # Add command handlers
            self.application.add_handler(CommandHandler("start", self._start_command))
            self.application.add_handler(CommandHandler("help", self._help_command))
            self.application.add_handler(CommandHandler("status", self._status_command))
            self.application.add_handler(CommandHandler("stats", self._stats_command))

            # Add message handler for general messages
            self.application.add_handler(
                MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
            )

            self.logger.info("Telegram bot initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize Telegram bot: {e}")
            raise

    def start(self):
        """Start the Telegram bot."""
        if not self.application:
            raise RuntimeError("Bot not initialized")

        if self.running:
            self.logger.warning("Telegram bot already running")
            return

        self.running = True
        self._bot_thread = threading.Thread(target=self._run_bot, daemon=True)
        self._bot_thread.start()
        self.logger.info("Telegram bot started")

    def stop(self):
        """Stop the Telegram bot."""
        self.running = False

        if self.application:
            try:
                # Stop the application
                asyncio.run(self.application.stop())
                asyncio.run(self.application.shutdown())
            except Exception as e:
                self.logger.error(f"Error stopping Telegram bot: {e}")

        if self._bot_thread and self._bot_thread.is_alive():
            self._bot_thread.join(timeout=5.0)

        self.logger.info("Telegram bot stopped")

    def _run_bot(self):
        """Run the bot in a separate thread."""
        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Run the bot
            self.application.run_polling(drop_pending_updates=True)

        except Exception as e:
            self.logger.error(f"Error running Telegram bot: {e}")
        finally:
            self.running = False

    async def _start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        welcome_message = (
            "🚗 Welcome to the Pothole Detection Bot!\n\n"
            "I will notify you when potholes are detected on the road.\n\n"
            "Available commands:\n"
            "/help - Show this help message\n"
            "/status - Show system status\n"
            "/stats - Show statistics"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=welcome_message)

    async def _help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        help_message = (
            "Available commands:\n"
            "/start - Start the bot\n"
            "/status - Show system status\n"
            "/stats - Show statistics"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=help_message)

    async def _status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command."""
        status_message = "The system is running smoothly."
        await context.bot.send_message(chat_id=update.effective_chat.id, text=status_message)

    async def _stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command."""
        # Here you would gather statistics from your system
        stats_message = "Statistics: [Placeholder for actual statistics]"
        await context.bot.send_message(chat_id=update.effective_chat.id, text=stats_message)

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle general messages."""
        user_message = update.message.text
        response_message = f"You said: {user_message}"
        await context.bot.send_message(chat_id=update.effective_chat.id, text=response_message)
