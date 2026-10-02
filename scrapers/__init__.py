from scrapers.france_travail import FranceTravailScraper
from scrapers.hellowork import HelloWorkScraper
from scrapers.meteojob import MeteojobScraper
from scrapers.distrijob import DistrijobScraper
from scrapers.adzuna import AdzunaScraper
from scrapers.leboncoin import LeboncoinScraper
from scrapers.interim import InterimScraper

def get_all_scrapers():
    """Возвращает список всех зарегистрированных скраперов вакансий во Франции."""
    return [
        FranceTravailScraper(),
        HelloWorkScraper(),
        MeteojobScraper(),
        DistrijobScraper(),
        AdzunaScraper(),
        LeboncoinScraper(),
        InterimScraper()
    ]
