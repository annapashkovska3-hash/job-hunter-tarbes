import os
import re
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class JobOffer(BaseModel):
    """Модель описания вакансии из любого источника."""
    id: str = Field(description="Уникальный ID вакансии с префиксом источника, например ft_1234")
    title: str = Field(description="Название должности")
    company: str = Field(default="Non spécifié", description="Компания-работодатель или агентство")
    location: str = Field(default="Tarbes (65000)", description="Город или адрес места работы")
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    distance_km: Optional[float] = Field(default=None, description="Расстояние в км от целевой точки")
    contract_type: str = Field(default="Non spécifié", description="Тип контракта: CDI, CDD, Intérim")
    salary: Optional[str] = Field(default=None, description="Зарплата (например, SMIC, 11.88€/h)")
    working_hours: Optional[str] = Field(default=None, description="График (35h, temps plein, 6h-13h)")
    description: str = Field(default="", description="Описание вакансии или выдержка")
    url: str = Field(description="Прямая ссылка для отклика/просмотра")
    source: str = Field(description="Источник: France Travail, HelloWork, Meteojob, Leboncoin, Adecco и др.")
    published_at: Optional[datetime] = None
    publication_date_str: Optional[str] = Field(default=None, description="Текст даты (например: Сегодня, Вчера, 3 дня назад)")
    age_days: Optional[float] = Field(default=None, description="Возраст вакансии в днях (0.0 = сегодня)")
    raw_data: Optional[dict] = Field(default=None, description="Сырые данные источника для отладки")

class CandidateProfile(BaseModel):
    """Профиль соискателя для персонализированного AI-анализа."""
    name: str = Field(default_factory=lambda: os.getenv("CANDIDATE_NAME", "Hanna Pashkovska"))
    phone: str = Field(default_factory=lambda: os.getenv("CANDIDATE_PHONE", ""))
    email: str = Field(default_factory=lambda: os.getenv("CANDIDATE_EMAIL", ""))
    location: str = "65000 Tarbes, France"
    mobility: str = "Vélo (Велосипед, радиус 10-15 км)"
    has_car: bool = False
    has_permis_b: bool = False
    french_level: str = "B1 (Intermédiaire professionnel)"
    other_languages: str = "Anglais (C2 courant), Russe (natif), Ukrainien (natif)"
    work_status: str = "APS (Autorisation provisoire de séjour avec droit au travail)"
    availability: str = "Disponible immédiatement (temps plein ou partiel)"
    experiences: List[str] = [
        "Employée Libre-Service chez Grand Frais Tarbes (Oct 2025 - Avr 2026): gestion des rayons frais, rotation des dates (DLC), réassort, inventaires, hygiène, conseil client",
        "Aide-cuisinière chez SUSHI E.Leclerc Ibos (Juin 2024 - Août 2024): respect strict des normes HACCP, hygiène alimentaire, travail en équipe",
        "Project Manager chez Soft Does (Jan 2025 - Juil 2025): organisation, rigueur, gestion des priorités et du temps"
    ]
    key_skills: List[str] = [
        "Mise en rayon et facing",
        "Gestion des stocks et inventaires",
        "Contrôle qualité et respect des règles d'hygiène / HACCP",
        "Préparation de commandes et conditionnement",
        "Rigueur, ponctualité, endurance physique et rapidité d'apprentissage"
    ]
    target_professions: List[str] = [
        "Employée Libre-Service",
        "Opératrice de conditionnement",
        "Préparatrice de commandes",
        "Agente de tri",
        "Employée polyvalente"
    ]

class MatchResult(BaseModel):
    """Результат оценки вакансии через Gemini AI."""
    compatibility: str = "GOOD"  # EXCELLENT, GOOD, CAUTION, NOT_RECOMMENDED
    badge: str = "🟢"            # 🟢, 🟡, 🔴
    summary_bullets: List[str] = Field(default_factory=list, description="Краткая суть вакансии на русском")
    alerts: List[str] = Field(default_factory=list, description="Предупреждения (например: нужен личный транспорт)")
    motivation_letter: str = Field(description="Готовое короткое письмо/отклик на французском для быстрой подачи")

class SearchSettings(BaseModel):
    """Настройки поискового агента."""
    city: str = "Tarbes"
    postal_code: str = "65000"
    radius_km: float = 15.0
    keywords: List[str] = [
        "employé libre-service",
        "mise en rayon",
        "opérateur de conditionnement",
        "préparateur de commandes",
        "agent de tri",
        "employé polyvalent"
    ]
    contract_types: List[str] = ["CDI", "CDD", "INTERIM", "MIS"]
    polling_interval_minutes: int = 10
    is_paused: bool = False

def is_strictly_relevant_job(title: str, description: str = "") -> bool:
    """
    Строгая фильтрация вакансий под профиль Ханны:
    - ИСКЛЮЧАЕТ: apprentissage/alternance, шефов/менеджеров, продавцов (vendeur).
    - ВКЛЮЧАЕТ: employé libre-service, mise en rayon, conditionnement, tri, préparation de commandes, employé polyvalent.
    """
    t_lower = title.lower()
    full_text = (title + " " + description).lower()

    # 1. СТРОЖАЙШИЙ ЧЕРНЫЙ СПИСОК (СТОП-СЛОВА)
    # Если ХОТЯ БЫ ОДНО из этих слов встречается в названии должности — МГНОВЕННЫЙ ОТКАЗ
    negative_keywords = [
        "apprentissage", "alternance", "apprenti", "stagiaire", "stage", "contrat pro", "cfa",
        "second", "seconde", "chef", "responsable", "manager", "directeur", "directrice", "adjoint", "adjointe", "superviseur",
        "vendeur", "vendeuse", "vente", "conseiller", "conseillère", "commercial",
        "cuisine", "dressing", "bricolage", "meuble", "conception",
        "poisson", "boucherie", "boucher", "boulangerie", "boulanger", "pâtissier", "charcuterie", "traiteur",
        "serveur", "serveuse", "barman", "plongeur",
        "médecin", "infirmier", "chirurgien", "aide-soignant", "pharmacien", "soin",
        "secrétaire", "comptable", "assistant", "assistante", "téléconseiller", "téléphonique"
    ]
    for neg in negative_keywords:
        if neg in t_lower:
            return False

    # Проверяем описание на стажировки и ученичество (apprentissage / alternance)
    apprentice_stop_words = ["apprentissage", "alternance", "contrat pro", "contrat de professionnalisation", "cfa", "stagiaire"]
    for app in apprentice_stop_words:
        if app in full_text:
            return False

    # 2. СТРОГИЕ ЦЕЛЕВЫЕ ПРОФЕССИИ (ПОЛОЖИТЕЛЬНЫЕ СОВПАДЕНИЯ)
    positive_keywords = [
        "libre-service", "libre service", "mise en rayon", "agent de rayon", "employé de rayon", "employée de rayon",
        "conditionnement", "conditionneuse", "opérateur de ligne", "opératrice de ligne", "agent de conditionnement",
        "préparateur de commande", "préparatrice de commande", "préparation de commande",
        "agent de tri", "agente de tri", "tri postal", "tri de",
        "employé polyvalent", "employée polyvalente", "agent logistique", "manutentionnaire"
    ]
    for pos in positive_keywords:
        if pos in t_lower:
            return True

    return False

def parse_french_job_age_days(text: str) -> float:
    """
    Определяет возраст вакансии в днях по тексту карточки или страницы:
    0.0 = сегодня / только что (aujourd'hui, il y a X heures/minutes)
    1.0 = вчера (hier, il y a 1 jour)
    > 1.0 = старше (il y a X jours)
    -1.0 = дата не указана
    """
    if not text:
        return -1.0
    import datetime
    t = text.lower()
    if "aujourd'hui" in t or "à l'instant" in t or "a l'instant" in t:
        return 0.0

    m_min = re.search(r'il y a\s+(\d+)\s*(?:minutes?|min)\b', t)
    if m_min:
        return round(float(m_min.group(1)) / 1440.0, 3)

    m_hr = re.search(r'il y a\s+(\d+)\s*(?:heures?|h)\b', t)
    if m_hr:
        return round(float(m_hr.group(1)) / 24.0, 2)

    if "hier" in t:
        return 1.0

    m_days = re.search(r'il y a\s+(\d+)\s*jour', t)
    if m_days:
        return float(m_days.group(1))

    m_plus = re.search(r'plus de\s+(\d+)\s*jour', t)
    if m_plus:
        return float(m_plus.group(1))

    m_date = re.search(r'(\d{2})/(\d{2})/(\d{4})', t)
    if m_date:
        d, m, y = map(int, m_date.groups())
        try:
            pub_date = datetime.date(y, m, d)
            today = datetime.date.today()
            return float((today - pub_date).days)
        except Exception:
            pass

    return -1.0

def format_job_publication_badge(age_days: Optional[float], raw_str: Optional[str] = None) -> str:
    """Форматирует плашку даты публикации для карточки Telegram."""
    if age_days is not None and age_days >= 0.0:
        if age_days <= 0.05:
            return "🔥 Только что (сегодня)"
        elif age_days < 1.0:
            return "⚡ Сегодня"
        elif age_days == 1.0:
            return "📅 Вчера"
        elif age_days > 1.0:
            return f"📅 {int(age_days)} дн. назад"
    if raw_str:
        return f"📅 {raw_str}"
    return "📅 Свежая"

