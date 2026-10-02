import asyncio
import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)

from core.models import CandidateProfile, SearchSettings
from core.database import JobDatabase
from core.ai_analyzer import AIJobAnalyzer
from bot.notifier import JobNotifier

logger = logging.getLogger(__name__)

class TelegramJobBot:
    """Интерактивный Telegram-бот для соискателя."""

    def __init__(self, token: str, db: JobDatabase, analyzer: AIJobAnalyzer, profile: CandidateProfile, settings: SearchSettings):
        self.token = token
        self.db = db
        self.analyzer = analyzer
        self.profile = profile
        self.settings = settings
        self.notifier = JobNotifier(db, analyzer, profile, settings)
        self.app = None
        self.background_task = None

    def build_app(self):
        self.app = ApplicationBuilder().token(self.token).build()

        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("check_now", self.cmd_check_now))
        self.app.add_handler(CommandHandler("profile", self.cmd_profile))
        self.app.add_handler(CommandHandler("settings", self.cmd_settings))
        self.app.add_handler(CommandHandler("favorites", self.cmd_favorites))
        self.app.add_handler(CommandHandler("pause", self.cmd_pause))
        self.app.add_handler(CommandHandler("resume", self.cmd_resume))

        self.app.add_handler(CallbackQueryHandler(self.handle_callback))
        return self.app

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = str(update.effective_chat.id)
        self.db.set_setting("chat_id", chat_id)
        logger.info(f"Зарегистрирован пользователь с chat_id: {chat_id}")

        text = (
            f"👋 <b>Bonjour Hanna ! Добро пожаловать!</b>\n\n"
            f"Я ваш персональный ассистент по поиску работы во Франции.\n"
            f"Я непрерывно сканирую все французские сайты вакансий (France Travail, HelloWork, Meteojob, Distrijob, агентства интерима) "
            f"и моментально присылаю новые вакансии прямо сюда.\n\n"
            f"📍 <b>Текущая локация:</b> {self.settings.city} ({self.settings.postal_code})\n"
            f"📏 <b>Радиус поиска:</b> {self.settings.radius_km} км\n"
            f"🚲 <b>Транспорт:</b> Велосипед (AI предупредит, если требуется авто/права)\n"
            f"⏱ <b>Интервал проверки:</b> каждые {self.settings.polling_interval_minutes} мин\n\n"
            f"Используйте кнопки ниже для управления:"
        )

        keyboard = [
            [InlineKeyboardButton("🔎 Проверить вакансии сейчас", callback_data="btn_check_now")],
            [InlineKeyboardButton("👤 Мой профиль", callback_data="btn_profile"), InlineKeyboardButton("⚙️ Радиус поиска", callback_data="btn_radius_menu")],
            [InlineKeyboardButton("⭐ Избранное", callback_data="btn_favorites"), InlineKeyboardButton("⏸️ Пауза / Пуск", callback_data="btn_toggle_pause")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_html(text, reply_markup=reply_markup)

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        stats = self.db.get_stats()
        is_paused = self.db.get_setting("is_paused", "0") == "1"
        status_icon = "⏸️ Приостановлен" if is_paused else "🟢 Активен (мониторит 24/7)"

        text = (
            f"📊 <b>Статус мониторинга:</b> {status_icon}\n\n"
            f"📍 <b>Зона поиска:</b> {self.settings.city} +{self.settings.radius_km} км\n"
            f"🎯 <b>Целевые профессии:</b> {len(self.settings.keywords)} позиций\n"
            f"📦 <b>Обработано вакансий в базе:</b> {stats['total_seen']}\n"
            f"⭐ <b>В избранном:</b> {stats['total_saved']}\n"
        )
        keyboard = [[InlineKeyboardButton("🔎 Проверить сейчас", callback_data="btn_check_now")]]
        await update.message.reply_html(text, reply_markup=InlineKeyboardMarkup(keyboard))

    async def cmd_check_now(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = str(update.effective_chat.id)
        msg = await update.message.reply_text("🔄 Сканирую France Travail, HelloWork, Meteojob, Distrijob... Ищу новые вакансии...")
        
        sent = await self.notifier.scan_and_notify(context.bot, chat_id)
        if sent > 0:
            await msg.edit_text(f"✅ Готово! Отправлено {sent} новых вакансий выше 👆")
        else:
            await msg.edit_text("👌 Все найденные вакансии уже были отправлены вам ранее. Новые появятся в течение нескольких минут.")

    async def cmd_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        p = self.profile
        text = (
            f"👤 <b>Профиль соискателя:</b>\n\n"
            f"<b>ФИО:</b> {p.name}\n"
            f"<b>Телефон:</b> {p.phone}\n"
            f"<b>Локация:</b> {p.location}\n"
            f"<b>Мобильность:</b> {p.mobility}\n"
            f"<b>Французский язык:</b> {p.french_level}\n"
            f"<b>Право на работу:</b> {p.work_status}\n\n"
            f"<b>Подтверждённый опыт в Тарбе:</b>\n"
            f"• <i>Grand Frais Tarbes</i> — Employée Libre-Service\n"
            f"• <i>E.Leclerc Ibos</i> — Aide-cuisinière / HACCP\n\n"
            f"<i>Каждое сопроводительное письмо автоматически опирается на эти данные.</i>"
        )
        await update.message.reply_html(text)

    async def cmd_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [
                InlineKeyboardButton("10 км", callback_data="set_radius_10"),
                InlineKeyboardButton("15 км (текущий)", callback_data="set_radius_15"),
                InlineKeyboardButton("20 км", callback_data="set_radius_20"),
                InlineKeyboardButton("30 км", callback_data="set_radius_30"),
            ]
        ]
        await update.message.reply_html(
            f"⚙️ <b>Настройки радиуса поиска вокруг Тарба:</b>\n\n"
            f"Текущий радиус: <b>{self.settings.radius_km} км</b>.\n"
            f"Выберите нужный радиус кнопкой:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def cmd_favorites(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        saved = self.db.get_saved_jobs()
        if not saved:
            await update.message.reply_text("⭐ У вас пока нет сохранённых вакансий. Нажимайте «⭐ В избранное» под любой вакансией.")
            return

        text = "⭐ <b>Ваши сохранённые вакансии:</b>\n\n"
        for s in saved[:10]:
            text += f"• <a href='{s['url']}'>{s['title']}</a> ({s['company']})\n"
        await update.message.reply_html(text, disable_web_page_preview=True)

    async def cmd_pause(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.db.set_setting("is_paused", "1")
        await update.message.reply_text("⏸️ Мониторинг вакансий приостановлен. Напишите /resume для продолжения.")

    async def cmd_resume(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.db.set_setting("is_paused", "0")
        await update.message.reply_text("▶️ Мониторинг вакансий возобновлён!")

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        data = query.data

        if data.startswith("save_"):
            job_id = data.replace("save_", "")
            # Ищем инфо о вакансии или сохраняем по id
            self.db.save_favorite_job(job_id, "Сохранённая вакансия", "Франция", "")
            await query.answer("⭐ Вакансия добавлена в избранное!", show_alert=True)

        elif data == "btn_check_now":
            chat_id = str(query.message.chat_id)
            await query.message.reply_text("🔄 Проверяю сайты вакансий...")
            sent = await self.notifier.scan_and_notify(context.bot, chat_id)
            if sent > 0:
                await query.message.reply_text(f"✅ Найдено и отправлено {sent} новых вакансий!")
            else:
                await query.message.reply_text("👌 Все актуальные вакансии уже были отправлены. Новые поступят автоматически.")

        elif data == "btn_profile":
            await self.cmd_profile(query, context)

        elif data == "btn_radius_menu":
            await self.cmd_settings(query, context)

        elif data.startswith("set_radius_"):
            r_val = float(data.replace("set_radius_", ""))
            self.settings.radius_km = r_val
            self.db.set_setting("radius_km", str(r_val))
            await query.edit_message_text(f"✅ Радиус поиска успешно изменён на <b>{r_val} км</b> вокруг Тарба!", parse_mode="HTML")

        elif data == "btn_favorites":
            await self.cmd_favorites(query, context)

        elif data == "btn_toggle_pause":
            is_paused = self.db.get_setting("is_paused", "0") == "1"
            if is_paused:
                self.db.set_setting("is_paused", "0")
                await query.message.reply_text("▶️ Мониторинг возобновлён!")
            else:
                self.db.set_setting("is_paused", "1")
                await query.message.reply_text("⏸️ Мониторинг приостановлен.")

    async def run_monitoring_loop(self):
        """Фоновый цикл проверки каждые X минут."""
        while True:
            try:
                chat_id = self.db.get_setting("chat_id") or os.getenv("TELEGRAM_CHAT_ID", "").strip()
                is_paused = self.db.get_setting("is_paused", "0") == "1"

                if chat_id and not is_paused and self.app:
                    logger.info("Запуск фоновой проверки вакансий...")
                    await self.notifier.scan_and_notify(self.app.bot, chat_id)
                elif not chat_id:
                    logger.info("Ожидание первого сообщения /start от пользователя для получения chat_id...")
            except Exception as e:
                logger.error(f"Ошибка в фоновом цикле мониторинга: {e}", exc_info=True)

            # Засыпаем на интервал (в минутах)
            interval_sec = self.settings.polling_interval_minutes * 60
            await asyncio.sleep(interval_sec)
