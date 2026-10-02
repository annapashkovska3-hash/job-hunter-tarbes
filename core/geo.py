import math
import logging
from typing import Optional, Tuple
import requests

logger = logging.getLogger(__name__)

# Координаты центра Тарба (Tarbes 65000)
DEFAULT_TARBES_COORDS = (43.2329, 0.0781)

# Кэш координат городов, чтобы не слать лишние запросы
_GEO_CACHE = {
    "tarbes": (43.2329, 0.0781),
    "65000": (43.2329, 0.0781),
    "ibos": (43.2333, 0.0000),
    "65420": (43.2333, 0.0000),
    "odos": (43.1969, 0.0583),
    "65310": (43.1969, 0.0583),
    "aureilhan": (43.2433, 0.0967),
    "65800": (43.2433, 0.0967),
    "séméac": (43.2286, 0.1039),
    "semeac": (43.2286, 0.1039),
    "65690": (43.2286, 0.1039),
    "laloubère": (43.2067, 0.0717),
    "laloubere": (43.2067, 0.0717),
    "65310": (43.2067, 0.0717),
    "bordères-sur-l'échez": (43.2608, 0.0489),
    "borderes-sur-l'echez": (43.2608, 0.0489),
    "65320": (43.2608, 0.0489),
    "juillan": (43.2017, 0.0217),
    "65290": (43.2017, 0.0217),
    "soues": (43.2067, 0.0989),
    "65430": (43.2067, 0.0989),
    "lourdes": (43.0944, -0.0458),
    "65100": (43.0944, -0.0458)
}

def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Вычисляет точное расстояние между двумя географическими точками по формуле Haversine."""
    R = 6371.0  # Радиус Земли в км
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (math.sin(d_lat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(d_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 1)

def resolve_french_coordinates(query: str) -> Optional[Tuple[float, float]]:
    """
    Определяет координаты любого французского города/индекса через официальный API
    (api-adresse.data.gouv.fr - бесплатно, мгновенно, без ключей).
    """
    clean_query = query.strip().lower()
    import re
    # Очищаем префиксы вида "65 - "
    clean_name = re.sub(r'^\d{2,5}\s*-\s*', '', clean_query).strip()
    if clean_query in _GEO_CACHE:
        return _GEO_CACHE[clean_query]
    if clean_name in _GEO_CACHE:
        return _GEO_CACHE[clean_name]

    # Попытка извлечь индекс из текста, например "Tarbes (65000)"
    import re
    zip_match = re.search(r'\b(65\d{3}|\d{5})\b', query)
    if zip_match:
        zip_code = zip_match.group(1)
        if zip_code in _GEO_CACHE:
            return _GEO_CACHE[zip_code]

    try:
        url = "https://api-adresse.data.gouv.fr/search/"
        params = {"q": query, "limit": 1}
        resp = requests.get(url, params=params, timeout=4)
        if resp.status_code == 200:
            data = resp.json()
            features = data.get("features", [])
            if features:
                coords = features[0]["geometry"]["coordinates"]
                # data.gouv возвращает [longitude, latitude]
                lon, lat = coords[0], coords[1]
                _GEO_CACHE[clean_query] = (lat, lon)
                return (lat, lon)
    except Exception as e:
        logger.warning(f"Ошибка при обращении к api-adresse для '{query}': {e}")

    return None

LOCAL_TARBES_COMMUNES = [
    "tarbes", "65000", "ibos", "65420", "odos", "65310", "aureilhan", "65800",
    "séméac", "semeac", "65600", "bordères-sur-l'échez", "borderes-sur-l'echez", "bordères", "borderes", "65320",
    "juillan", "65290", "soues", "65430", "louey", "ossun", "65380",
    "barbazan-debat", "barbazan", "65690", "orleix", "65390", "laloubère", "laloubere",
    "lourdes", "65100", "pontacq", "64530", "soumoulou", "64420"
]

def is_strictly_tarbes_area(text: str) -> bool:
    """Проверяет, относится ли текст или карточка строго к коммунам в радиусе 15 км от Тарба."""
    if not text:
        return False
    t = text.lower()
    return any(c in t for c in LOCAL_TARBES_COMMUNES)

def get_distance_from_tarbes(location_str: str, default_tarbes=DEFAULT_TARBES_COORDS) -> Optional[float]:
    """Возвращает расстояние в километрах от Тарба до указанной локации. Возвращает None, если локация не определена."""
    if not location_str or location_str.strip().lower() in ["", "non spécifié", "france", "france entière", "télétravail"]:
        return None

    loc_lower = location_str.lower().strip()
    
    # Строго Тарб
    if loc_lower in ["tarbes", "65000", "tarbes (65000)"]:
        return 0.0

    # Проверяем вхождение Тарба в строку, например "65 - Tarbes"
    import re
    if re.search(r'\btarbes\b', loc_lower):
        return 0.0

    coords = resolve_french_coordinates(location_str)
    if coords:
        return haversine_distance_km(default_tarbes[0], default_tarbes[1], coords[0], coords[1])
    
    return None
