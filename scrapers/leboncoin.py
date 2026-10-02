import re
import logging
from typing import List
import requests
from bs4 import BeautifulSoup

from core.models import JobOffer
from core.geo import get_distance_from_tarbes
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

class LeboncoinScraper(BaseScraper):
    """Скрапер объявлений о работе Leboncoin Emploi по Тарбу и 65 департаменту."""

    def __init__(self):
        super().__init__(name="Leboncoin")

    def fetch_offers(self, keywords: List[str], city: str = "Tarbes", postal_code: str = "65000", radius_km: float = 15.0) -> List[JobOffer]:
        results = []
        seen_ids = set()

        for kw in keywords:
            try:
                kw_encoded = kw.replace(" ", "+")
                url = f"https://www.leboncoin.fr/recherche?category=71&text={kw_encoded}&locations={city}_{postal_code}"
                resp = requests.get(url, headers=self.headers, timeout=10)
                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")
                links = soup.find_all("a", href=True)

                for link in links:
                    href = link["href"]
                    if not ("/offres_d_emploi/" in href or "/ad/" in href):
                        continue

                    id_match = re.search(r'/(\d+)\b', href)
                    if not id_match:
                        continue

                    job_id = f"lbc_{id_match.group(1)}"
                    if job_id in seen_ids:
                        continue
                    seen_ids.add(job_id)

                    title = link.get_text(" ", strip=True)
                    if not title or len(title) < 5:
                        continue

                    full_url = f"https://www.leboncoin.fr{href}" if href.startswith("/") else href
                    location = f"{city} ({postal_code})"
                    dist = get_distance_from_tarbes(location)

                    results.append(JobOffer(
                        id=job_id,
                        title=title,
                        company="Employeur local (Leboncoin)",
                        location=location,
                        distance_km=dist,
                        contract_type="Non spécifié",
                        description=title,
                        url=full_url,
                        source="Leboncoin"
                    ))

            except Exception as e:
                logger.warning(f"[Leboncoin] Ошибка по ключевому слову '{kw}': {e}")

        return results
