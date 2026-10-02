import re
import logging
from typing import List
import requests
from bs4 import BeautifulSoup

from core.models import JobOffer
from core.geo import get_distance_from_tarbes
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

class AdzunaScraper(BaseScraper):
    """Скрапер агрегатора Adzuna France."""

    def __init__(self):
        super().__init__(name="Adzuna")

    def fetch_offers(self, keywords: List[str], city: str = "Tarbes", postal_code: str = "65000", radius_km: float = 15.0) -> List[JobOffer]:
        results = []
        seen_ids = set()

        for kw in keywords:
            try:
                kw_encoded = kw.replace(" ", "+")
                url = f"https://www.adzuna.fr/search?q={kw_encoded}&w={city}&sort_by=date"
                resp = requests.get(url, headers=self.headers, timeout=10)
                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")
                links = soup.find_all("a", href=True)

                for link in links:
                    href = link["href"]
                    if not ("/land/ad/" in href or "/details/" in href):
                        continue

                    id_match = re.search(r'/ad/(\d+)', href) or re.search(r'/details/(\d+)', href)
                    if not id_match:
                        continue

                    job_id = f"adz_{id_match.group(1)}"
                    if job_id in seen_ids:
                        continue

                    raw_title = link.get_text(" ", strip=True)
                    if not raw_title or len(raw_title) < 5 or "voir" in raw_title.lower():
                        continue

                    # Проверяем релевантность
                    title_lower = raw_title.lower()
                    if not any(token in title_lower for token in ["libre", "service", "rayon", "tri", "condition", "prepar", "polyvalent", "magasin"]):
                        continue

                    seen_ids.add(job_id)

                    parent = link.find_parent("article") or link.find_parent("div")
                    card_text = parent.get_text(" ", strip=True) if parent else raw_title

                    # Определение контракта
                    contract = "Non spécifié"
                    for ct in ["CDI", "CDD", "Intérim"]:
                        if ct.lower() in card_text.lower():
                            contract = ct
                            break

                    from core.geo import is_strictly_tarbes_area
                    if not is_strictly_tarbes_area(card_text + " " + href):
                        continue

                    # Извлечение точной даты публикации
                    from core.models import parse_french_job_age_days
                    age = parse_french_job_age_days(card_text)
                    m_date = re.search(r'(aujourd[\'’]hui|hier|il y a\s+[^\s\|]+(?:\s+[^\s\|]+)?)', card_text, re.IGNORECASE)
                    date_str = m_date.group(0).strip() if m_date else None

                    # Определение коммуны
                    detected_loc = f"{city} ({postal_code})"
                    for com in ["ibos", "odos", "aureilhan", "séméac", "semeac", "bordères", "borderes", "juillan", "soues", "lourdes", "orleix", "tarbes"]:
                        if com in card_text.lower():
                            detected_loc = com.capitalize() + " (65)"
                            break

                    location = detected_loc
                    dist = get_distance_from_tarbes(location)

                    results.append(JobOffer(
                        id=job_id,
                        title=raw_title,
                        company="Partenaire Adzuna",
                        location=location,
                        distance_km=dist,
                        contract_type=contract,
                        description=card_text[:500],
                        url=href if href.startswith("http") else f"https://www.adzuna.fr{href}",
                        source="Adzuna",
                        publication_date_str=date_str,
                        age_days=age
                    ))

            except Exception as e:
                logger.warning(f"[Adzuna] Ошибка по ключевому слову '{kw}': {e}")

        return results
