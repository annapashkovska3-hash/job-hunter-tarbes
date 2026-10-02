import re
import logging
from typing import List
import requests
from bs4 import BeautifulSoup

from core.models import JobOffer
from core.geo import get_distance_from_tarbes
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

class DistrijobScraper(BaseScraper):
    """Скрапер специализированного портала ритейла и супермаркетов Distrijob (Intermarché, Aldi, Leclerc, Grand Frais)."""

    def __init__(self):
        super().__init__(name="Distrijob")
        self.category_urls = [
            "https://www.distrijob.fr/emploi/employe-de-libre-service.aspx",
            "https://www.distrijob.fr/emploi/agent-de-conditionnement.aspx",
            "https://www.distrijob.fr/emploi/preparateur-commande.aspx",
            "https://www.distrijob.fr/emploi/employe-polyvalent.aspx",
            "https://www.distrijob.fr/emploi/employe-de-rayon.aspx"
        ]

    def fetch_offers(self, keywords: List[str], city: str = "Tarbes", postal_code: str = "65000", radius_km: float = 15.0) -> List[JobOffer]:
        results = []
        seen_ids = set()

        for cat_url in self.category_urls:
            try:
                resp = requests.get(cat_url, headers=self.headers, timeout=10)
                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")
                links = soup.find_all("a", href=True)

                for link in links:
                    href = link["href"]
                    if not ("/offre-emploi/" in href and href.endswith(".aspx")):
                        continue

                    # Проверяем ID
                    id_match = re.search(r'-(\d+)\.aspx', href)
                    if not id_match:
                        continue

                    raw_id = id_match.group(1)
                    job_id = f"dj_{raw_id}"
                    if job_id in seen_ids:
                        continue

                    full_url = f"https://www.distrijob.fr{href}" if href.startswith("/") else href
                    link_text = link.get_text(" ", strip=True)

                    # Фильтр по региону: проверяем упоминание 65, Tarbes, Séméac, Ibos, Odos, Aureilhan
                    is_local = False
                    location_found = "Tarbes (65000)"
                    
                    target_localities = [
                        ("tarbes", "Tarbes (65000)"),
                        ("65000", "Tarbes (65000)"),
                        ("séméac", "Séméac (65600)"),
                        ("semeac", "Séméac (65600)"),
                        ("ibos", "Ibos (65420)"),
                        ("odos", "Odos (65310)"),
                        ("aureilhan", "Aureilhan (65800)"),
                        ("lourdes", "Lourdes (65100)"),
                        ("65400", "Ayzac-Ost (65400)"),
                        ("65420", "Ibos (65420)"),
                        ("65600", "Séméac (65600)")
                    ]

                    combined_text = (link_text + " " + href).lower()
                    for loc_key, loc_full in target_localities:
                        if loc_key in combined_text:
                            is_local = True
                            location_found = loc_full
                            break

                    if not is_local:
                        continue

                    seen_ids.add(job_id)

                    # Извлечение названия компании
                    company = "Grande Distribution"
                    for brand in ["Intermarché", "Aldi", "Lidl", "E.Leclerc", "Grand Frais", "Carrefour", "Système U", "Mousquetaires"]:
                        if brand.lower() in link_text.lower():
                            company = brand
                            break

                    # Заголовок
                    title = link_text.split("Emploi")[0].strip() if "Emploi" in link_text else link_text
                    if len(title) < 4:
                        title = "Employée Libre-Service / Rayon"

                    # Контракт
                    contract = "Non spécifié"
                    for ct in ["CDI", "CDD", "Intérim"]:
                        if ct in link_text:
                            contract = ct
                            break

                    dist = get_distance_from_tarbes(location_found)
                    if dist is not None and dist > radius_km + 3:
                        continue

                    results.append(JobOffer(
                        id=job_id,
                        title=title,
                        company=company,
                        location=location_found,
                        distance_km=dist,
                        contract_type=contract,
                        description=f"Offre Grande Distribution à {location_found} ({company})",
                        url=full_url,
                        source="Distrijob"
                    ))

            except Exception as e:
                logger.warning(f"[Distrijob] Ошибка при сборе с {cat_url}: {e}")

        return results
