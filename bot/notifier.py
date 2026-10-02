import asyncio
import logging
from typing import List, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Bot

from core.models import JobOffer, CandidateProfile, SearchSettings, is_strictly_relevant_job, format_job_publication_badge
from core.database import JobDatabase
from core.ai_analyzer import AIJobAnalyzer
from scrapers import get_all_scrapers

logger = logging.getLogger(__name__)

def format_telegram_card(offer: JobOffer, analysis) -> str:
    """Форматирует красивую, информативную карточку вакансии для Telegram."""
    # Эмодзи по типу работы
    title_lower = offer.title.lower()
    if "conditionnement" in title_lower:
        icon = "📦"
    elif "tri" in title_lower:
        icon = "📮"
    elif "commande" in title_lower:
        icon = "🛒"
    else:
        icon = "🏪"

    if offer.distance_km is not None and offer.distance_km > 0.0:
        dist_str = f" (~{offer.distance_km} км от Тарба)"
    elif offer.distance_km == 0.0:
        dist_str = " (г. Тарб)"
    else:
        dist_str = ""
    
    date_str = format_job_publication_badge(offer.age_days, offer.publication_date_str)
    
    # Карточка вакансии
    msg = (
        f"{icon} <b>{offer.title}</b>\n"
        f"🏢 <b>Компания:</b> {offer.company}\n"
        f"📍 <b>Локация:</b> {offer.location}{dist_str}\n"
        f"📅 <b>Опубликовано:</b> {date_str}\n"
        f"📄 <b>Контракт:</b> {offer.contract_type}\n"
        f"🌐 <b>Источник:</b> {offer.source}\n\n"
        f"{analysis.badge} <b>Оценка совместимости:</b> {analysis.compatibility}\n"
    )

    if analysis.summary_bullets:
        for b in analysis.summary_bullets:
            msg += f"• {b}\n"

    if analysis.alerts:
        msg += "\n"
        for a in analysis.alerts:
            msg += f"{a}\n"

    # Французский сопроводительный текст для моментального копирования
    msg += (
        f"\n📝 <b>Готовый текст для отклика (нажмите, чтобы скопировать):</b>\n"
        f"<code>{analysis.motivation_letter}</code>\n"
    )

    return msg

class JobNotifier:
    """Сервис опроса источников и отправки уведомлений соискателю."""

    def __init__(self, db: JobDatabase, analyzer: AIJobAnalyzer, profile: CandidateProfile, settings: SearchSettings):
        self.db = db
        self.analyzer = analyzer
        self.profile = profile
        self.settings = settings
        self.scrapers = get_all_scrapers()

    async def scan_and_notify(self, bot: Bot, chat_id: str) -> int:
        """Выполняет один цикл сканирования всех сайтов и отправляет новые вакансии."""
        if not chat_id:
            logger.warning("Chat ID не настроен. Пропуск отправки.")
            return 0

        logger.info(f"Начало поиска вакансий по {self.settings.city} ({self.settings.radius_km} км)...")
        all_new_offers: List[JobOffer] = []

        # Опрос всех зарегистрированных скраперов
        for scraper in self.scrapers:
            offers = scraper.safe_fetch(
                keywords=self.settings.keywords,
                city=self.settings.city,
                postal_code=self.settings.postal_code,
                radius_km=self.settings.radius_km
            )
            for off in offers:
                if not is_strictly_relevant_job(off.title, f"{off.description} {off.contract_type}"):
                    continue
                if off.distance_km is not None and off.distance_km > self.settings.radius_km + 3:
                    continue
                if off.age_days is not None and off.age_days > 1.0:
                    continue
                if not self.db.is_job_seen(off.id):
                    all_new_offers.append(off)

        logger.info(f"Найдено новых вакансий до отправки: {len(all_new_offers)}")

        sent_count = 0
        for offer in all_new_offers:
            # Сразу отмечаем в базе, чтобы избежать дублей
            self.db.mark_job_as_seen(
                job_id=offer.id,
                title=offer.title,
                company=offer.company,
                location=offer.location,
                source=offer.source,
                url=offer.url
            )

            # AI-анализ и составление французского текста отклика
            analysis = self.analyzer.analyze_offer(offer, self.profile)

            # Формирование карточки
            text = format_telegram_card(offer, analysis)

            # Инлайн-кнопки
            keyboard = [
                [
                    InlineKeyboardButton("🚀 Откликнуться (Перейти)", url=offer.url),
                    InlineKeyboardButton("⭐ В избранное", callback_data=f"save_{offer.id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                    disable_web_page_preview=False
                )
                sent_count += 1
                await asyncio.sleep(0.5)  # Защита от спам-лимитов Telegram
            except Exception as e:
                logger.error(f"Ошибка отправки вакансии {offer.id} в Telegram: {e}")

        logger.info(f"Успешно отправлено новых вакансий: {sent_count}")
        return sent_count
