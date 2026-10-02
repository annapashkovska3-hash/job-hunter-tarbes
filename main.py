import asyncio
import argparse
import logging
import sys
import os

# Настройка кодировки для Windows консоли
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from core import config
from core.database import JobDatabase
from core.ai_analyzer import AIJobAnalyzer
from bot.telegram_bot import TelegramJobBot
from bot.notifier import format_telegram_card, JobNotifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("JobHunterFrance")

async def run_scan_only():
    """Тестовый режим: разовое сканирование всех сайтов без Telegram-бота."""
    print("=" * 60)
    print("🔎 ТЕСТОВЫЙ РЕЖИМ СКАНИРОВАНИЯ ВАКАНСИЙ (ТАРБ 65000)")
    print("=" * 60)

    db = JobDatabase()
    profile = config.get_default_profile()
    settings = config.get_default_settings()
    analyzer = AIJobAnalyzer()
    notifier = JobNotifier(db, analyzer, profile, settings)

    print(f"Кандидат: {profile.name}")
    print(f"Город: {settings.city} (Радиус: {settings.radius_km} км)")
    print(f"Профессии: {', '.join(settings.keywords[:3])}...")
    print("Сканирование всех французских сайтов...")

    all_offers = []
    for scraper in notifier.scrapers:
        offers = scraper.safe_fetch(
            keywords=settings.keywords,
            city=settings.city,
            postal_code=settings.postal_code,
            radius_km=settings.radius_km
        )
        print(f"  -> [{scraper.name}]: найдено {len(offers)} вакансий")
        all_offers.extend(offers)

    print(f"\nВсего найдено вакансий со всех источников: {len(all_offers)}")
    print("-" * 60)

    # Демонстрация первых 3 карточек с анализом и текстом отклика
    displayed = 0
    for offer in all_offers:
        if displayed >= 3:
            break
        analysis = analyzer.analyze_offer(offer, profile)
        card = format_telegram_card(offer, analysis)
        print(f"\n--- ПРИМЕР КАРТОЧКИ #{displayed + 1} ---")
        # Убираем HTML-теги для красивого вывода в консоль
        clean_card = card.replace("<b>", "").replace("</b>", "").replace("<code>", ">>> ").replace("</code>", "")
        print(clean_card)
        print(f"Ссылка для отклика: {offer.url}")
        print("-" * 60)
        displayed += 1

    print("\n✅ Тестовое сканирование успешно завершено!")

async def run_bot():
    """Запуск полнофункционального Telegram-бота и фонового мониторинга."""
    token = config.TELEGRAM_BOT_TOKEN
    if not token or token == "your_telegram_bot_token_here":
        print("\n" + "!" * 60)
        print("ВНИМАНИЕ: TELEGRAM_BOT_TOKEN не задан в файле .env!")
        print("1. Откройте Telegram и напишите боту @BotFather")
        print("2. Отправьте команду /newbot и следуйте инструкциям")
        print("3. Скопируйте полученный токен в файл .env (строка TELEGRAM_BOT_TOKEN=...)")
        print("4. Для проверки работы парсеров прямо сейчас запустите: python main.py --scan-only")
        print("!" * 60 + "\n")
        return

    db = JobDatabase()
    profile = config.get_default_profile()
    settings = config.get_default_settings()
    analyzer = AIJobAnalyzer()

    bot_manager = TelegramJobBot(
        token=token,
        db=db,
        analyzer=analyzer,
        profile=profile,
        settings=settings
    )

    app = bot_manager.build_app()

    # Запуск фонового процесса опроса сайтов
    asyncio.create_task(bot_manager.run_monitoring_loop())

    logger.info("Запуск Telegram-бота... Нажмите Ctrl+C для остановки.")
    async with app:
        await app.start()
        await app.updater.start_polling()
        logger.info("Telegram-бот успешно запущен и слушает сообщения!")
        
        # Держим процесс активным
        while True:
            await asyncio.sleep(3600)

def main():
    parser = argparse.ArgumentParser(description="Персональный бот поиска работы во Франции")
    parser.add_argument("--scan-only", action="store_true", help="Разовый поиск вакансий и вывод в консоль без запуска бота")
    args = parser.parse_args()

    if args.scan_only:
        asyncio.run(run_scan_only())
    else:
        # Если токена нет, автоматически запускаем тест scan-only
        if not config.TELEGRAM_BOT_TOKEN or config.TELEGRAM_BOT_TOKEN == "your_telegram_bot_token_here":
            print("Токен бота пока не указан. Запускаем тестовое сканирование...")
            asyncio.run(run_scan_only())
        else:
            asyncio.run(run_bot())

if __name__ == "__main__":
    main()
