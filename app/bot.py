import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import datetime
import urllib.parse
import logging

import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)

from config import config
from database import PotholeDatabase
from models import Pothole

logger = logging.getLogger(__name__)

SEVERITY_EMOJIS = {
    'low': '🟢',
    'medium': '🟡',
    'high': '🟠',
    'critical': '🔴'
}


class PotholeBot:
    def __init__(self, db: PotholeDatabase):
        self.db = db
        self.application = Application.builder().token(config.BOT_TOKEN).build()
        self.setup_handlers()

    # ------------------------------------------------------------------ #
    # Handlers setup                                                       #
    # ------------------------------------------------------------------ #

    def setup_handlers(self):
        # Komande
        self.application.add_handler(CommandHandler('start', self.start))
        self.application.add_handler(CommandHandler('help', self.help_command))
        self.application.add_handler(CommandHandler('locations', self.display_locations))
        self.application.add_handler(CommandHandler('map', self.send_map))
        self.application.add_handler(CommandHandler('stats', self.send_stats))
        self.application.add_handler(CommandHandler('severity', self.display_by_severity))
        self.application.add_handler(CommandHandler('latest', self.send_latest))
        self.application.add_handler(CommandHandler('status', self.send_status))
        self.application.add_handler(CommandHandler('export', self.export_csv))

        # Callback handleri — regioni
        self.application.add_handler(CallbackQueryHandler(self.show_locations_in_region, pattern='^region:'))
        self.application.add_handler(CallbackQueryHandler(self.show_region_stats, pattern='^stats:'))
        self.application.add_handler(CallbackQueryHandler(self.back_to_regions, pattern='^back_to_regions$'))

        # Callback handleri — severity
        self.application.add_handler(CallbackQueryHandler(self.show_potholes_by_severity, pattern='^severity:'))
        self.application.add_handler(CallbackQueryHandler(self.back_to_severity_menu, pattern='^back_to_severity$'))

        # Callback handleri — latest / slike
        self.application.add_handler(CallbackQueryHandler(self.send_pothole_image, pattern='^image:'))

        # Callback handleri — help
        self.application.add_handler(CallbackQueryHandler(self.help_topic_handler, pattern='^help:(?!menu)'))
        self.application.add_handler(CallbackQueryHandler(self.help_menu_handler, pattern='^help:menu$'))

        # Callback handleri — ostalo
        self.application.add_handler(CallbackQueryHandler(self.send_location, pattern=r'^loc:'))
        self.application.add_handler(CallbackQueryHandler(self.noop_handler, pattern='^noop$'))

        # Sve nepoznate poruke — triggeruje start
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.unknown_message)
        )

    # ------------------------------------------------------------------ #
    # Pomocne funkcije                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _safe_float(value) -> float:
        try:
            if isinstance(value, bytes):
                value = value.decode('utf-8', errors='ignore')
            return float(value) if value is not None else 0.0
        except (ValueError, AttributeError):
            return 0.0

    def _is_admin(self, chat_id: int) -> bool:
        return self.db.get_user_role(chat_id) == 'admin'

    def _register(self, update: Update) -> str:
        """Registruje korisnika i vraca njegovu ulogu."""
        user = update.effective_user
        return self.db.register_user(
            chat_id=user.id,
            username=user.username or '',
            first_name=user.first_name or ''
        )

    def _main_keyboard(self) -> InlineKeyboardMarkup:
        """Glavna tastatura sa svim komandama kao dugmadi."""
        keyboard = [
            [
                InlineKeyboardButton("📍 Lokacije", callback_data="cmd:locations"),
                InlineKeyboardButton("🚨 Po težini", callback_data="cmd:severity"),
            ],
            [
                InlineKeyboardButton("🗺️ Mapa", callback_data="cmd:map"),
                InlineKeyboardButton("📊 Statistike", callback_data="cmd:stats"),
            ],
            [
                InlineKeyboardButton("🕒 Najnovije", callback_data="cmd:latest"),
                InlineKeyboardButton("📡 Status", callback_data="cmd:status"),
            ],
            [
                InlineKeyboardButton("📥 Export CSV", callback_data="cmd:export"),
                InlineKeyboardButton("❓ Pomoć", callback_data="help:menu"),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)

    # ------------------------------------------------------------------ #
    # Notifikacije (poziva main.py kad se detektuje nova rupa)            #
    # ------------------------------------------------------------------ #

    async def notify_new_pothole(self, pothole: Pothole):
        """
        Šalje notifikaciju svim adminima kad se detektuje HIGH ili CRITICAL rupa.
        Poziva se iz main.py nakon uspešnog upisa u bazu.
        """
        if pothole.severity.value not in ('high', 'critical'):
            return

        admin_ids = self.db.get_all_admin_chat_ids()
        if not admin_ids:
            return

        emoji = SEVERITY_EMOJIS.get(pothole.severity.value, '⚪')
        depth_cm = self._safe_float(pothole.depth) * 100

        message = (
            f"🚨 *Nova rupa detektovana!*\n\n"
            f"{emoji} Težina: *{pothole.severity.value.upper()}*\n"
            f"📍 Lokacija: {pothole.city}, {pothole.region}\n"
            f"📏 Dubina: {depth_cm:.1f}cm\n"
            f"🕒 {pothole.timestamp.strftime('%H:%M:%S')}\n\n"
            f"`{pothole.latitude:.5f}, {pothole.longitude:.5f}`"
        )

        keyboard = [[InlineKeyboardButton(
            "📍 Vidi na mapi",
            callback_data=f"loc:{pothole.latitude},{pothole.longitude}"
        )]]

        for chat_id in admin_ids:
            try:
                await self.application.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                # Ako postoji slika, posalji i nju
                if pothole.image_path and os.path.exists(pothole.image_path):
                    with open(pothole.image_path, 'rb') as img:
                        await self.application.bot.send_photo(
                            chat_id=chat_id,
                            photo=img,
                            caption=f"{emoji} {pothole.city} — {pothole.severity.value.upper()}"
                        )
            except Exception as e:
                logger.error(f"Greška pri slanju notifikacije adminu {chat_id}: {e}")

    # ------------------------------------------------------------------ #
    # Komande                                                              #
    # ------------------------------------------------------------------ #

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        role = self._register(update)
        user = update.effective_user
        stats = self.db.get_statistics()

        role_text = "👑 Admin" if role == 'admin' else "👤 Viewer"

        message = (
            f"*🚗 Sistem za detekciju rupa na putu*\n\n"
            f"Dobrodošao, *{user.first_name}*! {role_text}\n\n"
            f"📊 Trenutno u bazi:\n"
            f"• Ukupno rupa: *{stats['total']}*\n"
            f"• Danas detektovano: *{stats.get('today', 0)}*\n"
            f"• 🔴 Kritičnih: *{stats['by_severity'].get('critical', 0)}*\n\n"
            f"Izaberi akciju:"
        )

        await update.message.reply_text(
            message,
            parse_mode='Markdown',
            reply_markup=self._main_keyboard()
        )

    async def unknown_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Svaka nepoznata poruka triggeruje start."""
        await self.start(update, context)

    async def send_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        stats = self.db.get_statistics()
        total = stats['total']
        severity_stats = stats['by_severity']
        top_regions = stats['top_regions']
        today = stats.get('today', 0)

        message = (
            f"*📊 Statistike detekcije rupa*\n\n"
            f"Ukupno detektovano: *{total}*\n"
            f"Danas: *{today}*\n\n"
            f"*Po težini:*\n"
        )
        for severity, emoji in SEVERITY_EMOJIS.items():
            count = severity_stats.get(severity, 0)
            pct = (count / total * 100) if total > 0 else 0
            message += f"{emoji} {severity.capitalize()}: {count} ({pct:.0f}%)\n"

        if top_regions:
            message += "\n*Top regioni:*\n"
            for region, count in top_regions[:5]:
                message += f"• {region}: {count} rupa\n"

        keyboard = [[InlineKeyboardButton("🔙 Nazad", callback_data="cmd:menu")]]
        await update.message.reply_text(
            message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def send_map(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        potholes = self.db.get_potholes()
        if not potholes:
            await update.message.reply_text("Nema lokacija u bazi.")
            return

        base_url = "https://www.google.com/maps/dir/?api=1"
        locations = [f"{p.latitude},{p.longitude}" for p in potholes]
        destination = locations[0]
        waypoints = "|".join(locations[1:20])  # Google Maps limit

        url = f"{base_url}&destination={destination}"
        if waypoints:
            url += f"&waypoints={urllib.parse.quote(waypoints)}"

        message = (
            f"🗺️ *Mapa rupa na putu*\n\n"
            f"Prikazano lokacija: {min(len(potholes), 20)} od {len(potholes)}\n"
            f"[Otvori Google Maps]({url})"
        )
        await update.message.reply_text(message, parse_mode='Markdown')

    async def send_latest(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        potholes = self.db.get_latest_potholes(limit=5)
        if not potholes:
            await update.message.reply_text("Nema detektovanih rupa.")
            return

        message = "*🕒 Poslednjih 5 detektovanih rupa:*\n\n"
        keyboard = []

        for i, p in enumerate(potholes, 1):
            emoji = SEVERITY_EMOJIS.get(p.severity.value, '⚪')
            depth_cm = self._safe_float(p.depth) * 100
            message += (
                f"{i}. {emoji} *{p.severity.value.upper()}* — {p.city}, {p.region}\n"
                f"   📏 {depth_cm:.1f}cm | 🕒 {p.timestamp.strftime('%d.%m %H:%M')}\n\n"
            )

            row = [InlineKeyboardButton(
                f"📍 {p.city}",
                callback_data=f"loc:{p.latitude},{p.longitude}"
            )]
            if p.image_path and os.path.exists(p.image_path):
                row.append(InlineKeyboardButton(
                    f"📸 Slika",
                    callback_data=f"image:{p.id}"
                ))
            keyboard.append(row)

        keyboard.append([InlineKeyboardButton("🔙 Nazad", callback_data="cmd:menu")])
        await update.message.reply_text(
            message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def send_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        stats = self.db.get_statistics()
        user_counts = self.db.get_user_count()

        message = (
            f"*📡 Status sistema*\n\n"
            f"🟢 Bot: Aktivan\n"
            f"🗄️ Baza: {stats['total']} rupa\n"
            f"📅 Danas: {stats.get('today', 0)} novih\n\n"
            f"*Korisnici:*\n"
            f"👑 Admini: {user_counts.get('admin', 0)}\n"
            f"👤 Vieweri: {user_counts.get('viewer', 0)}\n\n"
            f"*Po težini:*\n"
        )
        for severity, emoji in SEVERITY_EMOJIS.items():
            count = stats['by_severity'].get(severity, 0)
            message += f"{emoji} {severity.capitalize()}: {count}\n"

        await update.message.reply_text(
            message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Nazad", callback_data="cmd:menu")
            ]])
        )

    async def display_locations(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        potholes = self.db.get_potholes()
        if not potholes:
            await update.message.reply_text("Nema lokacija u bazi.")
            return

        region_counts = {}
        for p in potholes:
            if p.region:
                region_counts[p.region] = region_counts.get(p.region, 0) + 1

        keyboard = []
        for region in sorted(region_counts.keys()):
            count = region_counts[region]
            keyboard.append([InlineKeyboardButton(
                f"📍 {region} ({count})",
                callback_data=f"region:{region}:all:0"
            )])
        keyboard.append([InlineKeyboardButton("🔙 Nazad", callback_data="cmd:menu")])

        await update.message.reply_text(
            "Izaberi region:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def display_by_severity(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        stats = self.db.get_statistics()
        severity_stats = stats.get('by_severity', {})

        keyboard = []
        for severity, emoji in SEVERITY_EMOJIS.items():
            count = severity_stats.get(severity, 0)
            keyboard.append([InlineKeyboardButton(
                f"{emoji} {severity.capitalize()} ({count})",
                callback_data=f"severity:{severity}:0"
            )])
        keyboard.append([InlineKeyboardButton(
            f"📊 Sve rupe ({stats.get('total', 0)})",
            callback_data="severity:all:0"
        )])
        keyboard.append([InlineKeyboardButton("🔙 Nazad", callback_data="cmd:menu")])

        await update.message.reply_text(
            "*🚨 Rupe po težini:*\n\nIzaberi nivo:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def export_csv(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        potholes = self.db.get_potholes()
        if not potholes:
            await update.message.reply_text("Nema podataka za export.")
            return

        data = [p.to_dict() for p in potholes]
        df = pd.DataFrame(data)

        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"rupe_export_{timestamp}.csv"
        filepath = os.path.join(config.EXPORT_DIR, filename)
        df.to_csv(filepath, index=False)

        with open(filepath, 'rb') as f:
            await update.message.reply_document(
                document=f,
                filename=filename,
                caption=f"📥 Export podataka\nUkupno zapisa: {len(df)}"
            )

    # ------------------------------------------------------------------ #
    # Callback handleri — glavni meni                                      #
    # ------------------------------------------------------------------ #

    async def _handle_cmd_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Jedan handler za sva dugmad iz glavnog menija."""
        query = update.callback_query
        await query.answer()
        cmd = query.data.split(":")[1]

        # Kreiramo fake update sa message-om da mozemo da pozovemo iste handlere
        if cmd == "locations":
            await self._edit_or_reply_locations(query)
        elif cmd == "severity":
            await self._edit_or_reply_severity(query)
        elif cmd == "map":
            await self._edit_or_reply_map(query)
        elif cmd == "stats":
            await self._edit_or_reply_stats(query)
        elif cmd == "latest":
            await self._edit_or_reply_latest(query)
        elif cmd == "status":
            await self._edit_or_reply_status(query)
        elif cmd == "export":
            await self._do_export(query)
        elif cmd == "menu":
            stats = self.db.get_statistics()
            user = query.from_user
            role = self.db.get_user_role(user.id) or 'viewer'
            role_text = "👑 Admin" if role == 'admin' else "👤 Viewer"
            message = (
                f"*🚗 Sistem za detekciju rupa na putu*\n\n"
                f"Dobrodošao, *{user.first_name}*! {role_text}\n\n"
                f"📊 Trenutno u bazi:\n"
                f"• Ukupno rupa: *{stats['total']}*\n"
                f"• Danas detektovano: *{stats.get('today', 0)}*\n"
                f"• 🔴 Kritičnih: *{stats['by_severity'].get('critical', 0)}*\n\n"
                f"Izaberi akciju:"
            )
            await query.message.edit_text(
                message,
                parse_mode='Markdown',
                reply_markup=self._main_keyboard()
            )

    async def _edit_or_reply_locations(self, query):
        potholes = self.db.get_potholes()
        if not potholes:
            await query.message.edit_text("Nema lokacija u bazi.")
            return

        region_counts = {}
        for p in potholes:
            if p.region:
                region_counts[p.region] = region_counts.get(p.region, 0) + 1

        keyboard = []
        for region in sorted(region_counts.keys()):
            keyboard.append([InlineKeyboardButton(
                f"📍 {region} ({region_counts[region]})",
                callback_data=f"region:{region}:all:0"
            )])
        keyboard.append([InlineKeyboardButton("🔙 Nazad", callback_data="cmd:menu")])
        await query.message.edit_text(
            "Izaberi region:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def _edit_or_reply_severity(self, query):
        stats = self.db.get_statistics()
        severity_stats = stats.get('by_severity', {})
        keyboard = []
        for severity, emoji in SEVERITY_EMOJIS.items():
            count = severity_stats.get(severity, 0)
            keyboard.append([InlineKeyboardButton(
                f"{emoji} {severity.capitalize()} ({count})",
                callback_data=f"severity:{severity}:0"
            )])
        keyboard.append([InlineKeyboardButton(
            f"📊 Sve ({stats.get('total', 0)})",
            callback_data="severity:all:0"
        )])
        keyboard.append([InlineKeyboardButton("🔙 Nazad", callback_data="cmd:menu")])
        await query.message.edit_text(
            "*🚨 Rupe po težini:*\n\nIzaberi nivo:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def _edit_or_reply_map(self, query):
        potholes = self.db.get_potholes()
        if not potholes:
            await query.message.edit_text("Nema lokacija u bazi.")
            return
        locations = [f"{p.latitude},{p.longitude}" for p in potholes]
        destination = locations[0]
        waypoints = "|".join(locations[1:20])
        url = f"https://www.google.com/maps/dir/?api=1&destination={destination}"
        if waypoints:
            url += f"&waypoints={urllib.parse.quote(waypoints)}"
        await query.message.edit_text(
            f"🗺️ *Mapa rupa*\n\nLokacija: {min(len(potholes), 20)} od {len(potholes)}\n[Otvori Google Maps]({url})",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Nazad", callback_data="cmd:menu")]])
        )

    async def _edit_or_reply_stats(self, query):
        stats = self.db.get_statistics()
        total = stats['total']
        message = (
            f"*📊 Statistike*\n\n"
            f"Ukupno: *{total}*\n"
            f"Danas: *{stats.get('today', 0)}*\n\n"
            f"*Po težini:*\n"
        )
        for severity, emoji in SEVERITY_EMOJIS.items():
            count = stats['by_severity'].get(severity, 0)
            pct = (count / total * 100) if total > 0 else 0
            message += f"{emoji} {severity.capitalize()}: {count} ({pct:.0f}%)\n"
        if stats['top_regions']:
            message += "\n*Top regioni:*\n"
            for region, count in stats['top_regions'][:5]:
                message += f"• {region}: {count}\n"
        await query.message.edit_text(
            message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Nazad", callback_data="cmd:menu")]])
        )

    async def _edit_or_reply_latest(self, query):
        potholes = self.db.get_latest_potholes(limit=5)
        if not potholes:
            await query.message.edit_text("Nema detektovanih rupa.")
            return
        message = "*🕒 Poslednjih 5 rupa:*\n\n"
        keyboard = []
        for i, p in enumerate(potholes, 1):
            emoji = SEVERITY_EMOJIS.get(p.severity.value, '⚪')
            depth_cm = self._safe_float(p.depth) * 100
            message += (
                f"{i}. {emoji} *{p.severity.value.upper()}* — {p.city}\n"
                f"   📏 {depth_cm:.1f}cm | {p.timestamp.strftime('%d.%m %H:%M')}\n\n"
            )
            row = [InlineKeyboardButton(f"📍 {p.city}", callback_data=f"loc:{p.latitude},{p.longitude}")]
            if p.image_path and os.path.exists(p.image_path):
                row.append(InlineKeyboardButton("📸 Slika", callback_data=f"image:{p.id}"))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 Nazad", callback_data="cmd:menu")])
        await query.message.edit_text(
            message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def _edit_or_reply_status(self, query):
        stats = self.db.get_statistics()
        user_counts = self.db.get_user_count()
        message = (
            f"*📡 Status sistema*\n\n"
            f"🟢 Bot: Aktivan\n"
            f"🗄️ Baza: {stats['total']} rupa\n"
            f"📅 Danas: {stats.get('today', 0)} novih\n\n"
            f"*Korisnici:*\n"
            f"👑 Admini: {user_counts.get('admin', 0)}\n"
            f"👤 Vieweri: {user_counts.get('viewer', 0)}\n\n"
            f"*Po težini:*\n"
        )
        for severity, emoji in SEVERITY_EMOJIS.items():
            message += f"{emoji} {severity.capitalize()}: {stats['by_severity'].get(severity, 0)}\n"
        await query.message.edit_text(
            message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Nazad", callback_data="cmd:menu")]])
        )

    async def _do_export(self, query):
        potholes = self.db.get_potholes()
        if not potholes:
            await query.answer("Nema podataka za export.", show_alert=True)
            return
        data = [p.to_dict() for p in potholes]
        df = pd.DataFrame(data)
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"rupe_export_{timestamp}.csv"
        filepath = os.path.join(config.EXPORT_DIR, filename)
        df.to_csv(filepath, index=False)
        with open(filepath, 'rb') as f:
            await query.message.reply_document(
                document=f,
                filename=filename,
                caption=f"📥 Export podataka\nUkupno zapisa: {len(df)}"
            )

    # ------------------------------------------------------------------ #
    # Callback handleri — regioni                                          #
    # ------------------------------------------------------------------ #

    async def show_locations_in_region(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()

        parts = query.data.split(":")
        region = parts[1]
        sort_by = parts[2] if len(parts) > 2 else "all"
        page = int(parts[3]) if len(parts) > 3 else 0
        ITEMS_PER_PAGE = 5

        filters = {'region': region}
        if sort_by != "all":
            filters['severity'] = sort_by

        potholes = self.db.get_potholes(filters=filters, sort_by='depth', sort_order='DESC')

        if not potholes:
            await query.message.edit_text(f"Nema rupa u regionu {region}.")
            return

        total_pages = (len(potholes) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        start_idx = page * ITEMS_PER_PAGE
        end_idx = min(start_idx + ITEMS_PER_PAGE, len(potholes))

        title = f"*📍 {region}*"
        if sort_by != "all":
            title += f" — {sort_by.capitalize()}"
        message = f"{title}\n_Strana {page+1}/{total_pages} • Ukupno: {len(potholes)}_\n\n"

        for i, p in enumerate(potholes[start_idx:end_idx], start=start_idx + 1):
            emoji = SEVERITY_EMOJIS.get(p.severity.value, '⚪')
            depth_cm = self._safe_float(p.depth) * 100
            area = self._safe_float(p.area)
            message += (
                f"{i}. {emoji} *{p.city}*\n"
                f"   Težina: {p.severity.value.capitalize()} | "
                f"📏 {depth_cm:.1f}cm | 📐 {area:.0f}px\n"
                f"   `{p.latitude:.4f}, {p.longitude:.4f}`\n\n"
            )

        keyboard = []

        # Filter dugmad
        filter_row = []
        for sev, emoji in SEVERITY_EMOJIS.items():
            if sort_by != sev:
                filter_row.append(InlineKeyboardButton(emoji, callback_data=f"region:{region}:{sev}:0"))
        if sort_by != "all":
            filter_row.insert(0, InlineKeyboardButton("📊 Sve", callback_data=f"region:{region}:all:0"))
        if filter_row:
            keyboard.append(filter_row)

        # Paginacija
        if total_pages > 1:
            nav = []
            if page > 0:
                nav.append(InlineKeyboardButton("⬅️", callback_data=f"region:{region}:{sort_by}:{page-1}"))
            nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
            if page < total_pages - 1:
                nav.append(InlineKeyboardButton("➡️", callback_data=f"region:{region}:{sort_by}:{page+1}"))
            keyboard.append(nav)

        # Lokacije i slike
        for p in potholes[start_idx:end_idx]:
            row = [InlineKeyboardButton(f"📍 {p.city}", callback_data=f"loc:{p.latitude},{p.longitude}")]
            if p.image_path and os.path.exists(p.image_path):
                row.append(InlineKeyboardButton("📸", callback_data=f"image:{p.id}"))
            keyboard.append(row)

        keyboard.append([InlineKeyboardButton("📊 Statistike regiona", callback_data=f"stats:{region}")])
        keyboard.append([InlineKeyboardButton("🔙 Nazad", callback_data="back_to_regions")])

        await query.message.edit_text(
            message, parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def show_region_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()

        region = query.data.split(":")[1]
        potholes = self.db.get_potholes(filters={'region': region})

        if not potholes:
            await query.message.edit_text(f"Nema statistika za {region}.")
            return

        severity_count = {}
        total_depth = total_area = 0.0
        for p in potholes:
            severity_count[p.severity.value] = severity_count.get(p.severity.value, 0) + 1
            total_depth += self._safe_float(p.depth)
            total_area += self._safe_float(p.area)

        avg_depth_cm = (total_depth / len(potholes)) * 100
        avg_area = total_area / len(potholes)

        message = f"*📊 Statistike — {region}*\n\nUkupno: {len(potholes)}\n\n*Po težini:*\n"
        for severity in ['critical', 'high', 'medium', 'low']:
            if severity in severity_count:
                emoji = SEVERITY_EMOJIS.get(severity, '⚪')
                count = severity_count[severity]
                pct = count / len(potholes) * 100
                message += f"{emoji} {severity.capitalize()}: {count} ({pct:.0f}%)\n"

        message += f"\n📏 Prosečna dubina: {avg_depth_cm:.1f}cm\n📐 Prosečna površina: {avg_area:.0f}px"

        await query.message.edit_text(
            message, parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Nazad", callback_data=f"region:{region}:all:0")
            ]])
        )

    async def back_to_regions(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        await self._edit_or_reply_locations(query)

    # ------------------------------------------------------------------ #
    # Callback handleri — severity                                         #
    # ------------------------------------------------------------------ #

    async def show_potholes_by_severity(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()

        parts = query.data.split(":")
        severity = parts[1]
        page = int(parts[2]) if len(parts) > 2 else 0
        ITEMS_PER_PAGE = 5

        if severity == "all":
            potholes = self.db.get_potholes(sort_by='severity', sort_order='DESC')
            title = "Sve rupe (po težini)"
        else:
            potholes = self.db.get_potholes(filters={'severity': severity}, sort_by='depth', sort_order='DESC')
            emoji = SEVERITY_EMOJIS.get(severity, '')
            title = f"{emoji} {severity.capitalize()} rupe"

        if not potholes:
            await query.message.edit_text(f"Nema rupa za izabrani nivo.")
            return

        total_pages = (len(potholes) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        start_idx = page * ITEMS_PER_PAGE
        end_idx = min(start_idx + ITEMS_PER_PAGE, len(potholes))

        message = f"*{title}*\n_Strana {page+1}/{total_pages} • Ukupno: {len(potholes)}_\n\n"

        for i, p in enumerate(potholes[start_idx:end_idx], start=start_idx + 1):
            emoji = SEVERITY_EMOJIS.get(p.severity.value, '⚪')
            depth_cm = self._safe_float(p.depth) * 100
            message += (
                f"{i}. {emoji} *{p.severity.value.upper()}* — {p.city}, {p.region}\n"
                f"   📏 {depth_cm:.1f}cm | {p.timestamp.strftime('%d.%m %H:%M')}\n\n"
            )

        keyboard = []

        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("⬅️", callback_data=f"severity:{severity}:{page-1}"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton("➡️", callback_data=f"severity:{severity}:{page+1}"))
        if nav:
            keyboard.append(nav)

        for p in potholes[start_idx:end_idx]:
            row = [InlineKeyboardButton(f"📍 {p.city}", callback_data=f"loc:{p.latitude},{p.longitude}")]
            if p.image_path and os.path.exists(p.image_path):
                row.append(InlineKeyboardButton("📸", callback_data=f"image:{p.id}"))
            keyboard.append(row)

        keyboard.append([InlineKeyboardButton("🔙 Nazad", callback_data="back_to_severity")])
        await query.message.edit_text(
            message, parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def back_to_severity_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        await self._edit_or_reply_severity(query)

    # ------------------------------------------------------------------ #
    # Callback handleri — slike i lokacije                                 #
    # ------------------------------------------------------------------ #

    async def send_pothole_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()

        pothole_id = int(query.data.split(":")[1])
        potholes = self.db.get_potholes()
        pothole = next((p for p in potholes if p.id == pothole_id), None)

        if not pothole or not pothole.image_path or not os.path.exists(pothole.image_path):
            await query.answer("Slika nije dostupna.", show_alert=True)
            return

        emoji = SEVERITY_EMOJIS.get(pothole.severity.value, '⚪')
        with open(pothole.image_path, 'rb') as img:
            await query.message.reply_photo(
                photo=img,
                caption=f"{emoji} *{pothole.severity.value.upper()}* — {pothole.city}, {pothole.region}\n"
                        f"📏 Dubina: {self._safe_float(pothole.depth)*100:.1f}cm\n"
                        f"🕒 {pothole.timestamp.strftime('%d.%m.%Y %H:%M')}",
                parse_mode='Markdown'
            )

    async def send_location(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        try:
            coords = query.data.replace("loc:", "")
            latitude, longitude = map(float, coords.split(","))
            await query.message.reply_location(latitude=latitude, longitude=longitude)
        except Exception as e:
            logger.error(f"Greška pri parsiranju lokacije: {e}")
            await query.answer("Greška pri učitavanju lokacije.", show_alert=True)

    async def noop_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.callback_query.answer()

    # ------------------------------------------------------------------ #
    # Help                                                                 #
    # ------------------------------------------------------------------ #

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        keyboard = [
            [InlineKeyboardButton("📍 Navigacija", callback_data="help:navigation")],
            [InlineKeyboardButton("📊 Podaci i statistike", callback_data="help:data")],
            [InlineKeyboardButton("🎯 Filteri", callback_data="help:filters")],
            [InlineKeyboardButton("🔔 Notifikacije", callback_data="help:notifications")],
            [InlineKeyboardButton("❓ FAQ", callback_data="help:faq")],
        ]
        await update.message.reply_text(
            "*❓ Centar za pomoć*\n\nIzaberi temu:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def help_topic_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        topic = query.data.split(":")[1]

        topics = {
            "navigation": (
                "*📍 Navigacija*\n\n"
                "• *Lokacije* — pregled rupa po regionu\n"
                "• *Mapa* — Google Maps link sa svim rupama\n"
                "• *Najnovije* — poslednjih 5 detektovanih\n"
                "• Dugme 📍 otvara pin na mapi\n"
                "• Dugme 📸 prikazuje sliku detekcije"
            ),
            "data": (
                "*📊 Podaci i statistike*\n\n"
                "• *Statistike* — ukupan pregled po težini i regionima\n"
                "• *Status* — stanje sistema i broj korisnika\n"
                "• *Export CSV* — preuzmi sve podatke\n"
                "• Polja: lokacija, težina, dubina, površina, vreme"
            ),
            "filters": (
                "*🎯 Filteri*\n\n"
                "• *Po težini* — filtriraj po nivou ozbiljnosti\n"
                f"  {SEVERITY_EMOJIS['low']} Low | {SEVERITY_EMOJIS['medium']} Medium | "
                f"{SEVERITY_EMOJIS['high']} High | {SEVERITY_EMOJIS['critical']} Critical\n"
                "• *Lokacije* → region → filter po težini unutar regiona\n"
                "• Paginacija po 5 rupa po strani"
            ),
            "notifications": (
                "*🔔 Notifikacije*\n\n"
                "• Admini automatski dobijaju poruku kad se detektuje\n"
                f"  {SEVERITY_EMOJIS['high']} HIGH ili {SEVERITY_EMOJIS['critical']} CRITICAL rupa\n"
                "• Notifikacija sadrži lokaciju, dubinu i sliku\n"
                "• Vieweri ne dobijaju notifikacije\n"
                "• Admin status se dodeljuje pri registraciji na osnovu chat ID-a"
            ),
            "faq": (
                "*❓ Česta pitanja*\n\n"
                "*Q: Kako postati admin?*\n"
                "A: Admin je unapred definisan u sistemu.\n\n"
                "*Q: Zašto neke rupe nemaju sliku?*\n"
                "A: Slika se čuva samo kad je detekcija uspešna.\n\n"
                "*Q: Kolika je tačnost detekcije?*\n"
                "A: Confidence score je prikazan po rupi u exportu.\n\n"
                "*Q: Šta znači 'Unknown' lokacija?*\n"
                "A: GPS signal nije bio dostupan u tom trenutku."
            ),
        }

        message = topics.get(topic, "Tema nije pronađena.")
        await query.message.edit_text(
            message, parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Nazad", callback_data="help:menu")
            ]])
        )

    async def help_menu_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        keyboard = [
            [InlineKeyboardButton("📍 Navigacija", callback_data="help:navigation")],
            [InlineKeyboardButton("📊 Podaci i statistike", callback_data="help:data")],
            [InlineKeyboardButton("🎯 Filteri", callback_data="help:filters")],
            [InlineKeyboardButton("🔔 Notifikacije", callback_data="help:notifications")],
            [InlineKeyboardButton("❓ FAQ", callback_data="help:faq")],
            [InlineKeyboardButton("🔙 Glavni meni", callback_data="cmd:menu")],
        ]
        await query.message.edit_text(
            "*❓ Centar za pomoć*\n\nIzaberi temu:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ------------------------------------------------------------------ #
    # Run                                                                  #
    # ------------------------------------------------------------------ #

    def setup_cmd_handler(self):
        """Registruje handler za cmd: callbacks — poziva se posle setup_handlers."""
        self.application.add_handler(CallbackQueryHandler(self._handle_cmd_callback, pattern='^cmd:'))

    def run(self):
        self.setup_cmd_handler()
        self.application.run_polling()