import datetime
from asyncio.windows_events import NULL

import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import logging

from config import config
from database import PotholeDatabase
from models import Pothole

logger = logging.getLogger(__name__)

class PotholeBot:
    def __init__(self, db: PotholeDatabase):
        self.db = db
        self.application = Application.builder().token(config.BOT_TOKEN).build()
        self.setup_handlers()

    def setup_handlers(self):
        """Set up bot command handlers"""
        self.application.add_handler(CommandHandler('start', self.start))
        self.application.add_handler(CommandHandler('locations', self.display_locations))
        self.application.add_handler(CommandHandler('map', self.send_map))
        self.application.add_handler(CommandHandler('stats', self.send_stats))
        self.application.add_handler(CallbackQueryHandler(self.show_locations_in_region, pattern='^region:'))
        self.application.add_handler(CallbackQueryHandler(self.send_location))
        self.application.add_handler(CommandHandler('severity', self.display_by_severity))
        self.application.add_handler(CallbackQueryHandler(self.show_potholes_by_severity, pattern='^severity:'))
        self.application.add_handler(CommandHandler('export', self.export_csv))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send welcome message"""
        message = (
            "*🚗 Pothole Info Bot 🚗*\n\n"
            "Welcome! This bot helps you track detected potholes.\n\n"
            "*Available Commands:*\n"
            "/start - Show this help message\n"
            "/locations - Browse pothole locations by region\n"
            "/map - Get a Google Maps link with all locations\n"
            "/stats - View detection statistics\n\n"
            "Stay safe on the roads! 🛣️"
        )
        await update.message.reply_text(message, parse_mode='Markdown')

    async def send_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send detection statistics"""
        stats = self.db.get_statistics()
        total = stats['total']
        severity_stats = stats['by_severity']
        top_regions = stats['top_regions']

        message = f"*📊 Pothole Detection Statistics*\n\nTotal Potholes Detected: {total}\n"
        for severity, count in severity_stats.items():
            message += f"{severity.capitalize()}: {count}\n"

        message += "\n*Top Regions:*\n"
        for region, count in top_regions:
            message += f"• {region}: {count} potholes\n"

        await update.message.reply_text(message, parse_mode='Markdown')

    async def send_map(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send Google Maps link with all pothole locations"""
        potholes = self.db.get_potholes()
        if not potholes:
            await update.message.reply_text("No pothole locations available.")
            return

        base_url = "https://www.google.com/maps/dir/?api=1"
        locations = [f"{p.latitude},{p.longitude}" for p in potholes]
        destination = locations[0]
        waypoints = "|".join(locations[1:])

        url = f"{base_url}&destination={destination}"
        if waypoints:
            import urllib
            url += f"&waypoints={urllib.parse.quote(waypoints)}"

        message = f"📍 *Pothole Locations Map*\n\nTotal locations: {len(potholes)}\n"
        message += f"[View on Google Maps]({url})"
        await update.message.reply_text(message, parse_mode='Markdown')

    async def display_locations(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Display regions with pothole detections"""
        regions = self.db.get_potholes(filters={'region': NULL})  # Get unique regions
        if not regions:
            await update.message.reply_text("No pothole locations available.")
            return

        keyboard = []
        for region in sorted(set(p.region for p in regions)):
            count = len([p for p in regions if p.region == region])
            button_text = f"{region} ({count} potholes)"
            callback_data = f"region:{region}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Select a region to view pothole locations:",
            reply_markup=reply_markup
        )

    async def show_locations_in_region(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show locations in selected region"""
        query = update.callback_query
        await query.answer()

        region = query.data.split(":")[1]
        potholes = self.db.get_potholes(filters={'region': region})

        if not potholes:
            await query.message.reply_text(f"No potholes found in {region}.")
            return

        keyboard = []
        for pothole in potholes:
            button_text = f"📍 {pothole.city} ({pothole.latitude:.4f}, {pothole.longitude:.4f})"
            callback_data = f"{pothole.latitude},{pothole.longitude}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            f"*Potholes in {region}:*\nTap a location to view on map.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    async def send_location(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send specific location"""
        query = update.callback_query
        await query.answer()

        try:
            latitude, longitude = map(float, query.data.split(","))
            await query.message.reply_location(latitude=latitude, longitude=longitude)
        except ValueError:
            await query.message.reply_text("Invalid location data.")

    def run(self):
        """Start the bot"""
        self.application.run_polling()

    async def display_by_severity(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Display potholes sorted by severity"""
        keyboard = [
            [InlineKeyboardButton("🟢 Low Severity", callback_data="severity:low")],
            [InlineKeyboardButton("🟡 Medium Severity", callback_data="severity:medium")],
            [InlineKeyboardButton("🟠 High Severity", callback_data="severity:high")],
            [InlineKeyboardButton("🔴 Critical Severity", callback_data="severity:critical")],
            [InlineKeyboardButton("📊 All Potholes", callback_data="severity:all")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Select severity level to view potholes:",
            reply_markup=reply_markup
        )

    async def show_potholes_by_severity(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show potholes filtered by severity"""
        query = update.callback_query
        await query.answer()

        severity = query.data.split(":")[1]

        if severity == "all":
            potholes = self.db.get_potholes(sort_by='severity', sort_order='DESC')
        else:
            potholes = self.db.get_potholes(filters={'severity': severity}, sort_by='depth', sort_order='DESC')
        if not potholes:
            await query.message.reply_text(f"No {severity} severity potholes found.")
            return

        message = f"*{severity.capitalize()} Severity Potholes:*\n\n"
        for p in potholes[:10]:  # Show top 10
            message += f"📍 {p.city}, {p.region}\n"
            message += f"   Depth: {p.depth:.3f}m | Area: {p.area:.0f}px\n"
            message += f"   Location: ({p.latitude:.4f}, {p.longitude:.4f})\n\n"

        await query.message.reply_text(message, parse_mode='Markdown')

    async def export_csv(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        import os

        potholes = self.db.get_potholes()
        if not potholes:
            await update.message.reply_text("No data to export.")
            return

        # Convert to DataFrame
        data = [p.to_dict() for p in potholes]
        df = pd.DataFrame(data)

        # Create CSV file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"potholes_export_{timestamp}.csv"
        filepath = os.path.join(config.EXPORT_DIR, filename)

        df.to_csv(filepath, index=False)

        # Send file
        with open(filepath, 'rb') as f:
            await update.message.reply_document(
                document=f,
                filename=filename,
                caption=f"Pothole data export\nTotal records: {len(df)}"
            )