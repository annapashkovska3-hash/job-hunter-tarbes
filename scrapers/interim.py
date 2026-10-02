import re
import logging
from typing import List
import requests
from bs4 import BeautifulSoup

from core.models import JobOffer
from core.geo import get_distance_from_tarbes
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

class InterimScraper(BaseScraper):
    """Скрапер предложений агентств интерима (Adecco, Manpower, Randstad, Crit, Proman в Тарбе)."""

    def __init__(self):
        super().__init__(name="Agences Intérim Tarbes")

    def fetch_offers(self, keywords: List[str], city: str = "Tarbes", postal_code: str = "65000", radius_km: float = 15.0) -> List[JobOffer]:
        results = []
        seen_ids = set()

        # Поиск именно временных контрактов (intérim / mission temporaire)
        for kw in keywords:
            try:
                # Поиск на France Travail с фильтром по контракту Intérim (typeContrat=MIS) и сортировкой по дате (tri=1)
                url = f"https://candidat.francetravail.fr/offres/recherche?lieux=65440&motsCles={kw}&natureContrat=E2&rayon={int(radius_km)}&typeContrat=MIS&tri=1"
                resp = requests.get(url, headers=self.headers, timeout=10)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    offers = soup.find_all("li", class_="result")

                    for el in offers:
                        link_el = el.find("a", href=True)
                        if not link_el:
                            continue

                        href = link_el["href"]
                        full_url = f"https://candidat.francetravail.fr{href}" if href.startswith("/") else href
                        id_match = re.search(r'/detail/([A-Za-z0-9]+)', href)
                        raw_id = id_match.group(1) if id_match else str(abs(hash(full_url)))
                        job_id = f"interim_{raw_id}"

                        if job_id in seen_ids:
                            continue
                        seen_ids.add(job_id)

                        title_el = el.find("h2") or el.find("h3") or link_el
                        title = title_el.get_text(strip=True) if title_el else kw

                        card_text = el.get_text(" | ", strip=True)

                        # Извлечение точной даты публикации
                        from core.models import parse_french_job_age_days
                        age = parse_french_job_age_days(card_text)
                        m_date = re.search(r'Publi[ée]\s+([^\|]+)', card_text)
                        date_str = m_date.group(0).strip() if m_date else None

                        sub_el = el.find("p", class_="subtext") or el.find("p")
                        raw_sub = sub_el.get_text() if sub_el else ""
                        loc_match = re.search(r'(\d{2}\s*-\s*([^\n\r]+))', raw_sub)
                        if loc_match:
                            location = loc_match.group(1).strip()
                            comp_part = raw_sub.split(loc_match.group(1))[0].strip()
                            agency_name = re.sub(r'[\s\-]+$', '', comp_part).strip() or "Agence d'Intérim (Tarbes)"
                        else:
                            location = f"{city} ({postal_code})"

                        desc_el = el.find("p", class_="description")
                        desc = desc_el.get_text(" ", strip=True) if desc_el else raw_sub

                        dist = get_distance_from_tarbes(location)

                        results.append(JobOffer(
                            id=job_id,
                            title=title,
                            company=agency_name,
                            location=location,
                            distance_km=dist,
                            contract_type="Intérim",
                            description=desc,
                            url=full_url,
                            source=f"Intérim ({agency_name})",
                            publication_date_str=date_str,
                            age_days=age
                        ))

            except Exception as e:
                logger.warning(f"[Interim] Ошибка по '{kw}': {e}")

        return results
