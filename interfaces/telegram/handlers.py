import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from core.data.repository import PotholeRepository
from config import settings
import folium
import os
from datetime import datetime

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message"""
    welcome_msg = """
    🚧 *Pothole Detection Bot* 🚧

    Welcome! I help track and report potholes detected by our system.

    Commands:
    /start - Show this message
    /map - Get map with all pothole locations
    /locations - List potholes by region

    Stay safe on the roads!
    """
    await update.message.reply_text(welcome_msg, parse_mode="Markdown")


async def send_map(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send map with pothole locations"""
    repo = PotholeRepository(settings.data_file)
    potholes = repo.get_all_potholes()

    if not potholes:
        await update.message.reply_text("No pothole locations available")
        return

    # Create interactive map
    m = folium.Map(location=[potholes[0].location.latitude, potholes[0].location.longitude], zoom_start=12)

    for pothole in potholes:
        folium.Marker(
            [pothole.location.latitude, pothole.location.longitude],
            popup=f"{pothole.city}, {pothole.region}",
            icon=folium.Icon(color='red', icon='info-sign')
        ).add_to(m)

    # Save temporary map
    map_file = "pothole_map.html"
    m.save(map_file)

    # Send as document
    await update.message.reply_document(
        document=open(map_file, 'rb'),
        caption="Pothole Locations Map"
    )

    # Clean up
    os.remove(map_file)


async def show_regions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show regions with potholes"""
    repo = PotholeRepository(settings.data_file)
    potholes = repo.get_all_potholes()

    regions = {p.region for p in potholes}
    if not regions:
        await update.message.reply_text("No regions available")
        return

    keyboard = [
        [InlineKeyboardButton(region, callback_data=f"region:{region}")]
        for region in sorted(regions)
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Select a region:", reply_markup=reply_markup)


async def handle_region_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle region selection callback"""
    query = update.callback_query
    await query.answer()

    region = query.data.split(":")[1]
    repo = PotholeRepository(settings.data_file)
    potholes = [p for p in repo.get_all_potholes() if p.region == region]

    if not potholes:
        await query.edit_message_text(f"No potholes found in {region}")
        return

    response = [f"🚧 *Potholes in {region}* 🚧\n"]
    for i, pothole in enumerate(potholes[:10]):  # Limit to first 10
        response.append(
            f"{i + 1}. {pothole.city} - "
            f"{pothole.location.latitude:.6f}, {pothole.location.longitude:.6f}"
        )

    await query.edit_message_text("\n".join(response), parse_mode="Markdown")


def register_handlers(application):
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("map", send_map))
    application.add_handler(CommandHandler("locations", show_regions))
    application.add_handler(CallbackQueryHandler(handle_region_selection, pattern="^region:"))