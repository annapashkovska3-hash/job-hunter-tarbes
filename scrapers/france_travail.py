import re
import logging
from typing import List
import requests
from bs4 import BeautifulSoup

from core.models import JobOffer
from core.geo import get_distance_from_tarbes
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

class FranceTravailScraper(BaseScraper):
    """Скрапер официальной государственной платформы France Travail (Pôle Emploi)."""

    def __init__(self):
        super().__init__(name="France Travail")

    def fetch_offers(self, keywords: List[str], city: str = "Tarbes", postal_code: str = "65000", radius_km: float = 15.0) -> List[JobOffer]:
        results = []
        seen_ids = set()

        # Для Тарба код коммуны в France Travail - 65440, или по департаменту 65D
        location_code = "65440" if "tarbes" in city.lower() or postal_code == "65000" else postal_code

        for kw in keywords:
            try:
                url = f"https://candidat.francetravail.fr/offres/recherche?lieux={location_code}&motsCles={kw}&rayon={int(radius_km)}&tri=1"
                resp = requests.get(url, headers=self.headers, timeout=10)
                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")
                offer_elements = soup.find_all("li", class_="result")

                for el in offer_elements:
                    # Извлечение ссылки и ID
                    link_el = el.find("a", href=True)
                    if not link_el:
                        continue

                    href = link_el["href"]
                    full_url = f"https://candidat.francetravail.fr{href}" if href.startswith("/") else href
                    
                    # ID вакансии из URL
                    id_match = re.search(r'/detail/([A-Za-z0-9]+)', href)
                    job_id = f"ft_{id_match.group(1)}" if id_match else f"ft_{abs(hash(full_url))}"

                    if job_id in seen_ids:
                        continue
                    seen_ids.add(job_id)

                    # Заголовок
                    title_el = el.find("h2") or el.find("h3") or link_el
                    title = title_el.get_text(strip=True) if title_el else kw

                    card_text = el.get_text(" | ", strip=True)

                    # Извлечение точной даты публикации
                    from core.models import parse_french_job_age_days
                    age = parse_french_job_age_days(card_text)
                    m_date = re.search(r'Publi[ée]\s+([^\|]+)', card_text)
                    date_str = m_date.group(0).strip() if m_date else None

                    # Компания и локация
                    sub_el = el.find("p", class_="subtext") or el.find("p")
                    raw_sub = sub_el.get_text() if sub_el else ""
                    
                    company = "Non spécifié"
                    location = "Tarbes (65000)"
                    
                    loc_match = re.search(r'(\d{2}\s*-\s*([^\n\r]+))', raw_sub)
                    if loc_match:
                        location = loc_match.group(1).strip()
                        comp_part = raw_sub.split(loc_match.group(1))[0].strip()
                        company = re.sub(r'[\s\-]+$', '', comp_part).strip() or "Non spécifié"
                    else:
                        location = f"{city} ({postal_code})"

                    # Описание или выдержка
                    desc_el = el.find("p", class_="description")
                    description = desc_el.get_text(" ", strip=True) if desc_el else raw_sub

                    # Контракт
                    contract = "Non spécifié"
                    for ct in ["CDI", "CDD", "MIS", "Intérim"]:
                        if ct.lower() in (title + " " + description).lower():
                            contract = "Intérim" if ct == "MIS" else ct
                            break

                    # Расстояние от Тарба
                    dist = get_distance_from_tarbes(location)

                    # Фильтр по радиусу, если удалось рассчитать расстояние
                    if dist is not None and dist > radius_km + 3:
                        continue

                    results.append(JobOffer(
                        id=job_id,
                        title=title,
                        company=company,
                        location=location,
                        distance_km=dist,
                        contract_type=contract,
                        description=description,
                        url=full_url,
                        source="France Travail",
                        publication_date_str=date_str,
                        age_days=age
                    ))

            except Exception as e:
                logger.warning(f"[France Travail] Ошибка по ключевому слову '{kw}': {e}")

        return results
