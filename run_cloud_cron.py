import asyncio
import logging
import os
import sys

# Настройка кодировки для вывода
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("CloudJobMonitor")

from core import config
from core.database import JobDatabase
from core.ai_analyzer import AIJobAnalyzer
from core.models import CandidateProfile, SearchSettings
from bot.notifier import JobNotifier
from telegram import Bot

async def main():
    logger.info("=" * 60)
    logger.info("🚀 ЗАПУСК ОБЛАЧНОГО МОНИТОРИНГА ВАКАНСИЙ (GITHUB ACTIONS)")
    logger.info("=" * 60)

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip() or config.TELEGRAM_BOT_TOKEN
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip() or config.TELEGRAM_CHAT_ID
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip() or config.GEMINI_API_KEY

    city = os.getenv("DEFAULT_CITY", "Tarbes")
    postal_code = os.getenv("DEFAULT_POSTAL_CODE", "65000")
    radius_km = float(os.getenv("DEFAULT_RADIUS_KM", "15"))

    if not token or not chat_id:
        logger.error("❌ TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID не настроены в Secrets!")
        sys.exit(1)

    # Инициализация базы данных
    db = JobDatabase()
    
    # Инициализация профиля и настроек
    profile = CandidateProfile()
    settings = SearchSettings(
        city=city,
        postal_code=postal_code,
        radius_km=radius_km
    )

    analyzer = AIJobAnalyzer(api_key=gemini_key)
    notifier = JobNotifier(db, analyzer, profile, settings)

    logger.info(f"Кандидат: {profile.name}")
    logger.info(f"Локация: {settings.city} ({settings.postal_code}), радиус {settings.radius_km} км")
    logger.info(f"Поиск строго свежих вакансий (сегодня/24ч)...")

    bot = Bot(token=token)
    sent_count = await notifier.scan_and_notify(bot, chat_id)

    logger.info("=" * 60)
    logger.info(f"✅ Цикл сканирования завершен! Отправлено новых вакансий: {sent_count}")
    logger.info("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
