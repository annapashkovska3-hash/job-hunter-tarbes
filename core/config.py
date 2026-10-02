import os
from pathlib import Path
from dotenv import load_dotenv
from core.models import CandidateProfile, SearchSettings

# Загрузка .env файла
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

DEFAULT_CITY = os.getenv("DEFAULT_CITY", "Tarbes")
DEFAULT_POSTAL_CODE = os.getenv("DEFAULT_POSTAL_CODE", "65000")
DEFAULT_RADIUS_KM = float(os.getenv("DEFAULT_RADIUS_KM", "15"))
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "5"))

FRANCE_TRAVAIL_CLIENT_ID = os.getenv("FRANCE_TRAVAIL_CLIENT_ID", "").strip()
FRANCE_TRAVAIL_CLIENT_SECRET = os.getenv("FRANCE_TRAVAIL_CLIENT_SECRET", "").strip()

def get_default_profile() -> CandidateProfile:
    """Возвращает актуальный профиль соискателя Ханны."""
    return CandidateProfile()

def get_default_settings() -> SearchSettings:
    """Возвращает настройки поиска по умолчанию для Тарба."""
    return SearchSettings(
        city=DEFAULT_CITY,
        postal_code=DEFAULT_POSTAL_CODE,
        radius_km=DEFAULT_RADIUS_KM,
        polling_interval_minutes=CHECK_INTERVAL_MINUTES
    )
