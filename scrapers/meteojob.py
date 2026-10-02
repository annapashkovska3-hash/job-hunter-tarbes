import re
import logging
from typing import List
import requests
from bs4 import BeautifulSoup

from core.models import JobOffer
from core.geo import get_distance_from_tarbes
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

class MeteojobScraper(BaseScraper):
    """Скрапер платформы Meteojob."""

    def __init__(self):
        super().__init__(name="Meteojob")

    def fetch_offers(self, keywords: List[str], city: str = "Tarbes", postal_code: str = "65000", radius_km: float = 15.0) -> List[JobOffer]:
        results = []
        seen_ids = set()

        for kw in keywords:
            try:
                kw_encoded = kw.replace(" ", "+")
                url = f"https://www.meteojob.com/jobs?what={kw_encoded}&where={city}"
                resp = requests.get(url, headers=self.headers, timeout=10)
                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")
                links = soup.find_all("a", href=True)

                for link in links:
                    href = link["href"]
                    id_match = re.search(r'/jobs/(\d+)', href)
                    if not id_match:
                        continue

                    job_id = f"mj_{id_match.group(1)}"
                    if job_id in seen_ids:
                        continue
                    seen_ids.add(job_id)

                    full_url = f"https://www.meteojob.com{href}" if href.startswith("/") else href
                    title = link.get_text(" ", strip=True)
                    if not title or len(title) < 4:
                        continue

                    # Фильтрация нерелевантных заголовков (например, если meteojob выкинул врача)
                    kw_lower = kw.lower()
                    title_lower = title.lower()
                    if not any(token in title_lower for token in ["libre", "service", "rayon", "tri", "condition", "prepar", "polyvalent", "magasin"]):
                        continue

                    parent = link.find_parent("li") or link.find_parent("article") or link.find_parent("div")
                    card_text = parent.get_text(" ", strip=True) if parent else title

                    # Определение контракта
                    contract = "Non spécifié"
                    for ct in ["CDI", "CDD", "Intérim"]:
                        if ct.lower() in card_text.lower():
                            contract = ct
                            break

                    from core.geo import is_strictly_tarbes_area
                    if not is_strictly_tarbes_area(card_text + " " + full_url):
                        continue

                    # Определение коммуны
                    detected_loc = f"{city} ({postal_code})"
                    for com in ["ibos", "odos", "aureilhan", "séméac", "semeac", "bordères", "borderes", "juillan", "soues", "lourdes", "orleix", "tarbes"]:
                        if com in card_text.lower():
                            detected_loc = com.capitalize() + " (65)"
                            break

                    location = detected_loc
                    dist = get_distance_from_tarbes(location)

                    # Извлечение точной даты публикации
                    from core.models import parse_french_job_age_days
                    age = parse_french_job_age_days(card_text)
                    m_date = re.search(r'(aujourd[\'’]hui|hier|il y a\s+[^\s\|]+(?:\s+[^\s\|]+)?)', card_text, re.IGNORECASE)
                    date_str = m_date.group(0).strip() if m_date else None

                    results.append(JobOffer(
                        id=job_id,
                        title=title,
                        company="Meteojob Partner",
                        location=location,
                        distance_km=dist,
                        contract_type=contract,
                        description=card_text[:500],
                        url=full_url,
                        source="Meteojob",
                        publication_date_str=date_str,
                        age_days=age
                    ))

            except Exception as e:
                logger.warning(f"[Meteojob] Ошибка по ключевому слову '{kw}': {e}")

        return results
