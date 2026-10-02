import os
import json
import logging
import re
from typing import Optional
from core import config
from core.models import JobOffer, CandidateProfile, MatchResult

logger = logging.getLogger(__name__)

class AIJobAnalyzer:
    """Анализ вакансий и генерация текстов отклика через Google Gemini (с надёжным fallback)."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.GEMINI_API_KEY
        self.client = None
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Не удалось инициализировать Google GenAI клиент: {e}")

    def analyze_offer(self, offer: JobOffer, profile: CandidateProfile) -> MatchResult:
        """Анализирует соответствие вакансии профилю Ханны и генерирует текст отклика."""
        if self.client:
            try:
                return self._analyze_with_gemini(offer, profile)
            except Exception as e:
                logger.error(f"Ошибка Gemini API при анализе вакансии: {e}. Используем локальный анализатор.")

        return self._analyze_local_rule_based(offer, profile)

    def _analyze_with_gemini(self, offer: JobOffer, profile: CandidateProfile) -> MatchResult:
        sign_line = f"{profile.name} - {profile.phone}" if profile.phone else profile.name
        prompt = f"""
Tu es un expert du recrutement et de l'emploi en France (secteur commerce, logistique, intérim).
Analyse cette offre d'emploi pour la candidate suivante :

PROFIL DE LA CANDIDATE :
- Nom : {profile.name}
- Ville : {profile.location}
- Mobilité : {profile.mobility} (Pas de voiture, pas de permis B).
- Niveau de français : {profile.french_level}
- Statut : {profile.work_status}
- Expériences clés :
  * Employée Libre-Service chez Grand Frais Tarbes (oct 2025 - avr 2026) : gestion des rayons frais, rotation DLC, réassort, inventaires, hygiène, conseil client.
  * Aide-cuisinière chez SUSHI E.Leclerc Ibos (juin 2024 - août 2024) : normes HACCP, hygiène, travail d'équipe.
  * Project Manager chez Soft Does : rigueur, gestion des priorités.

OFFRE D'EMPLOI :
- Titre : {offer.title}
- Entreprise : {offer.company}
- Lieu : {offer.location} (Distance : {offer.distance_km or 'Non précisée'} km)
- Contrat : {offer.contract_type}
- Horaires/Salaire : {offer.working_hours or ''} / {offer.salary or ''}
- Description : {offer.description[:1500]}

TÂCHES :
1. Évaluer la compatibilité :
   - "EXCELLENT" avec badge "🟢" si correspond parfaitement (employée libre-service, tri, conditionnement, mise en rayon, logistique accessible).
   - "CAUTION" avec badge "🟡" si des conditions particulières existent (ex: permis B recommandé mais pas obligatoire, horaires très matinaux).
   - "NOT_RECOMMENDED" avec badge "🔴" UNIQUEMENT si le permis B / véhicule personnel est STRICTEMENT obligatoire et le lieu inaccessible à vélo.
2. Extraire 2-3 points clés en russe (bullet points) : horaires, mission principale, spécificités.
3. Rédiger un message d'accroche / motivation en FRANÇAIS, court (3 à 4 phrases max), percutant, professionnel et prêt à l'emploi.
   Ce message doit :
   - Mentionner directement son expérience concrète chez Grand Frais Tarbes ou E.Leclerc Ibos.
   - Souligner sa disponibilité immédiate et son sérieux.
   - Être signé "{sign_line}".

RÉPONDS STRICTEMENT AU FORMAT JSON SUIVANT (sans balises markdown supplémentaires) :
{{
  "compatibility": "EXCELLENT" ou "CAUTION" ou "NOT_RECOMMENDED",
  "badge": "🟢" ou "🟡" или "🔴",
  "summary_bullets": ["Пункт 1", "Пункт 2"],
  "alerts": ["Предупреждение, если есть (например: требуется личный транспорт)"],
  "motivation_letter": "Texte court en français prêt à être copié..."
}}
"""
        response = None
        for m_name in ["gemini-3.5-flash-lite", "gemini-flash-latest", "gemini-3.5-flash"]:
            try:
                response = self.client.models.generate_content(
                    model=m_name,
                    contents=prompt,
                )
                if response and response.text:
                    break
            except Exception as e:
                logger.warning(f"Модель {m_name} недоступна: {e}")

        if not response or not response.text:
            raise ValueError("Ни одна из моделей Gemini не смогла сгенерировать ответ")
        text = response.text.strip()
        # Извлечение JSON
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
            return MatchResult(
                compatibility=data.get("compatibility", "GOOD"),
                badge=data.get("badge", "🟢"),
                summary_bullets=data.get("summary_bullets", []),
                alerts=data.get("alerts", []),
                motivation_letter=data.get("motivation_letter", "")
            )

        raise ValueError("Не удалось распарсить JSON ответ Gemini")

    def _analyze_local_rule_based(self, offer: JobOffer, profile: CandidateProfile) -> MatchResult:
        """Быстрый локальный анализ на случай отсутствия ключа Gemini."""
        desc_lower = (offer.title + " " + offer.description).lower()
        
        alerts = []
        badge = "🟢"
        compatibility = "GOOD"

        # Проверка на требования к транспорту
        if "permis b" in desc_lower or "véhicule exigé" in desc_lower or "véhiculé" in desc_lower:
            alerts.append("⚠️ В описании упоминается Permis B / личный транспорт")
            badge = "🟡"
            compatibility = "CAUTION"

        # Проверка на ночные смены
        if "nuit" in desc_lower or "horaires décalés" in desc_lower or "3x8" in desc_lower:
            alerts.append("⏰ Нестандартный график (смены / ночь)")

        # Формирование тезисов
        bullets = []
        if offer.contract_type and offer.contract_type != "Non spécifié":
            bullets.append(f"Контракт: {offer.contract_type}")
        if offer.distance_km is not None:
            bullets.append(f"Расстояние от Тарба: ~{offer.distance_km} км")
        if offer.company and offer.company != "Non spécifié":
            bullets.append(f"Работодатель: {offer.company}")

        # Генерация качественного французского текста отклика
        title_lower = offer.title.lower()
        sign_block = f"Cordialement,\n{profile.name}"
        if profile.phone:
            sign_block += f"\nTél : {profile.phone}"

        if "conditionnement" in title_lower or "opérat" in title_lower:
            mot_text = (
                f"Bonjour,\n\n"
                f"Vivement intéressée par votre offre d'{offer.title}, je vous propose ma candidature. "
                f"Rigoureuse, dynamique et habituée au respect strict des consignes et des cadences, "
                f"j'ai une expérience réussie en grande distribution (Grand Frais Tarbes) et en agroalimentaire (E.Leclerc Ibos). "
                f"Disponible immédiatement sur Tarbes, je serais ravie de rejoindre vos équipes.\n\n"
                f"{sign_block}"
            )
        elif "rayon" in title_lower or "libre-service" in title_lower or "magasin" in title_lower:
            mot_text = (
                f"Bonjour,\n\n"
                f"Forte de mon expérience réussie en tant qu'Employée Libre-Service chez Grand Frais à Tarbes, "
                f"je maîtrise parfaitement la mise en rayon, la rotation des dates (DLC), le réassort et l'accueil client. "
                f"Organisée, ponctuelle et disponible immédiatement, je saurai m'adapter rapidement à votre établissement. "
                f"Je reste à votre entière disposition pour tout échange.\n\n"
                f"{sign_block}"
            )
        elif "tri" in title_lower or "postal" in title_lower:
            mot_text = (
                f"Bonjour,\n\n"
                f"Attentive, méthodique et dynamique, je postule avec enthousiasme au poste de {offer.title}. "
                f"À l'aise avec les tâches actives nécessitant précision et cadence, et forte d'expériences pratiques à Tarbes "
                f"(Grand Frais et E.Leclerc), je suis immédiatement disponible.\n\n"
                f"{sign_block}"
            )
        else:
            mot_text = (
                f"Bonjour,\n\n"
                f"Je vous adresse ma candidature pour le poste de {offer.title}. "
                f"Dynamique, polyvalente et forte d'expériences réussies à Tarbes (Grand Frais, E.Leclerc Ibos), "
                f"je fais preuve d'une grande rigueur et d'une excellente capacité d'adaptation. "
                f"Je suis immédiatement disponible pour démarrer.\n\n"
                f"{sign_block}"
            )

        return MatchResult(
            compatibility=compatibility,
            badge=badge,
            summary_bullets=bullets,
            alerts=alerts,
            motivation_letter=mot_text
        )
