import re
import logging
from typing import List
import requests
from bs4 import BeautifulSoup

from core.models import JobOffer
from core.geo import get_distance_from_tarbes
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

class HelloWorkScraper(BaseScraper):
    """Скрапер платформы HelloWork."""

    def __init__(self):
        super().__init__(name="HelloWork")

    def fetch_offers(self, keywords: List[str], city: str = "Tarbes", postal_code: str = "65000", radius_km: float = 15.0) -> List[JobOffer]:
        results = []
        seen_ids = set()

        for kw in keywords:
            try:
                kw_encoded = kw.replace(" ", "+")
                url = f"https://www.hellowork.com/fr-fr/emploi/recherche.html?k={kw_encoded}&l={city}+{postal_code}&ray={int(radius_km)}&tri=date"
                resp = requests.get(url, headers=self.headers, timeout=10)
                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")
                links = soup.find_all("a", href=True)

                for link in links:
                    href = link["href"]
                    if not ("/fr-fr/emplois/" in href and href.endswith(".html")):
                        continue

                    id_match = re.search(r'/emplois/(\d+)\.html', href)
                    if not id_match:
                        continue

                    job_id = f"hw_{id_match.group(1)}"
                    if job_id in seen_ids:
                        continue
                    seen_ids.add(job_id)

                    full_url = f"https://www.hellowork.com{href}" if href.startswith("/") else href
                    raw_text = link.get_text(" ", strip=True)
                    if not raw_text or len(raw_text) < 4:
                        continue

                    # Извлечение информации из текста ссылки или родительской карточки
                    parent = link.find_parent("li") or link.find_parent("div")
                    full_card_text = parent.get_text(" ", strip=True) if parent else raw_text

                    # Извлечение точной даты публикации
                    from core.models import parse_french_job_age_days
                    age = parse_french_job_age_days(full_card_text)
                    m_date = re.search(r'(aujourd[\'’]hui|hier|il y a\s+[^\s\|]+(?:\s+[^\s\|]+)?)', full_card_text, re.IGNORECASE)
                    date_str = m_date.group(0).strip() if m_date else None

                    # Попытка извлечь компанию
                    company = "Non spécifié"
                    for brand in ["E.Leclerc", "Grand Frais", "Carrefour", "Intermarché", "Aldi", "Lidl", "Adecco", "Manpower", "Randstad", "Proman", "Crit", "Stokomani", "Action"]:
                        if brand.lower() in full_card_text.lower():
                            company = brand
                            break

                    contract = "Non spécifié"
                    for ct in ["CDI", "CDD", "Intérim", "Alternance", "Stage"]:
                        if ct.lower() in full_card_text.lower():
                            contract = ct
                            break

                    from core.geo import is_strictly_tarbes_area

                    # Проверяем, что вакансия относится строго к зоне Тарба и окрестностям (не из других регионов!)
                    if not is_strictly_tarbes_area(full_card_text + " " + full_url):
                        continue

                    # Извлечение коммуны
                    detected_loc = f"{city} ({postal_code})"
                    for com in ["ibos", "odos", "aureilhan", "séméac", "semeac", "bordères", "borderes", "juillan", "soues", "lourdes", "orleix", "tarbes"]:
                        if com in full_card_text.lower():
                            detected_loc = com.capitalize() + " (65)"
                            break

                    location = detected_loc
                    dist = get_distance_from_tarbes(location)

                    results.append(JobOffer(
                        id=job_id,
                        title=raw_text,
                        company=company,
                        location=location,
                        distance_km=dist,
                        contract_type=contract,
                        description=full_card_text[:500],
                        url=full_url,
                        source="HelloWork",
                        publication_date_str=date_str,
                        age_days=age
                    ))

            except Exception as e:
                logger.warning(f"[HelloWork] Ошибка по ключевому слову '{kw}': {e}")

        return results
