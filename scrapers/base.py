import abc
import logging
from typing import List
from core.models import JobOffer

logger = logging.getLogger(__name__)

class BaseScraper(abc.ABC):
    """Базовый абстрактный класс для всех скраперов вакансий."""

    def __init__(self, name: str):
        self.name = name
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
        }

    @abc.abstractmethod
    def fetch_offers(self, keywords: List[str], city: str = "Tarbes", postal_code: str = "65000", radius_km: float = 15.0) -> List[JobOffer]:
        """Получить список вакансий по критериям."""
        pass

    def safe_fetch(self, keywords: List[str], city: str = "Tarbes", postal_code: str = "65000", radius_km: float = 15.0) -> List[JobOffer]:
        """Безопасный вызов fetch_offers с перехватом любых ошибок, чтобы не ломать весь пайплайн."""
        try:
            offers = self.fetch_offers(keywords, city, postal_code, radius_km)
            logger.info(f"[{self.name}] Найдено вакансий: {len(offers)}")
            return offers
        except Exception as e:
            logger.error(f"[{self.name}] Ошибка при сборе вакансий: {e}", exc_info=False)
            return []
