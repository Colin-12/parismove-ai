"""Orchestrateur principal du coach.

Pipeline :
    1. Classifier l'intent de la question (modèle 8B léger)
    2. Selon l'intent, appeler les tools data-aware appropriés
    3. Construire un contexte riche avec les données récupérées
    4. Demander au LLM (modèle 70B) de générer une réponse en français/anglais
       en s'appuyant uniquement sur le contexte
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import Engine

from coach.intent import IntentResult, IntentType, classify_intent
from coach.llm import LLMClient
from coach.prompts import get_system_prompt
from coach.tools import (
    get_current_air_quality,
    get_current_traffic,
    get_current_weather,
    list_capabilities,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CoachResponse:
    """Réponse complète du coach pour une question."""

    answer: str
    intent: IntentType
    language: str
    tools_used: list[str]
    has_real_data: bool


class Coach:
    """Coach mobilité orchestrateur des sous-systèmes."""

    def __init__(
        self,
        engine: Engine,
        llm: LLMClient,
        small_model: str | None = None,
    ) -> None:
        self._engine = engine
        self._llm = llm
        self._small_model = small_model

    def ask(self, question: str) -> CoachResponse:
        """Répond à une question utilisateur."""
        intent_result = classify_intent(
            question, self._llm, model=self._small_model
        )
        logger.info(
            "intent_classified",
            extra={
                "intent": intent_result.intent.value,
                "language": intent_result.language,
            },
        )

        context, tools_used = self._gather_context(question, intent_result)
        has_real_data = any("[DATA]" in c for c in context)

        # Réponse finale via LLM 70B
        system_prompt = get_system_prompt(intent_result.language)
        context_block = "\n\n".join(context) if context else "(aucune donnée)"

        user_message = (
            f"QUESTION : {question}\n\n"
            f"CONTEXTE :\n{context_block}\n\n"
            f"Réponds maintenant à la question en t'appuyant uniquement sur le contexte."
        )

        answer = self._llm.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ]
        )

        return CoachResponse(
            answer=answer.strip(),
            intent=intent_result.intent,
            language=intent_result.language,
            tools_used=tools_used,
            has_real_data=has_real_data,
        )

    def _gather_context(
        self, question: str, intent: IntentResult
    ) -> tuple[list[str], list[str]]:
        """Selon l'intent, appelle les bons tools et collecte le contexte.

        Returns:
            Tuple (liste de blocs de contexte, liste des noms de tools utilisés)
        """
        contexts: list[str] = []
        tools_used: list[str] = []

        if intent.intent == IntentType.GREETING:
            return [], []

        if intent.intent == IntentType.HELP:
            contexts.append(list_capabilities())
            tools_used.append("list_capabilities")
            return contexts, tools_used

        if intent.intent == IntentType.AIR_QUALITY:
            zone = self._extract_zone(question)
            contexts.append(get_current_air_quality(self._engine, zone=zone))
            tools_used.append("get_current_air_quality")
            return contexts, tools_used

        if intent.intent == IntentType.WEATHER:
            point = self._extract_zone(question)
            contexts.append(get_current_weather(self._engine, point=point))
            tools_used.append("get_current_weather")
            return contexts, tools_used

        if intent.intent == IntentType.TRAFFIC:
            line = self._extract_line(question)
            contexts.append(get_current_traffic(self._engine, line_query=line))
            tools_used.append("get_current_traffic")
            return contexts, tools_used

        # journey_score / journey_compare : pour ces intents, on a besoin de
        # waypoints précis que l'utilisateur n'a probablement pas fournis dans
        # une question conversationnelle. On guide alors l'utilisateur vers
        # la commande CLI dédiée.
        if intent.intent in (IntentType.JOURNEY_SCORE, IntentType.JOURNEY_COMPARE):
            contexts.append(
                "[GUIDE] Le scoring de trajets nécessite des coordonnées GPS "
                "précises. Pour un trajet entre A et B, utilise la commande :\n"
                '  healthscore score --journey-id mon-trajet --label "..." '
                '--point lat1,lon1 --point lat2,lon2\n'
                "Pour comparer 2 trajets :\n"
                '  healthscore compare --journey "id:label:lat,lon:lat,lon" '
                '--journey "..."\n'
                "Le coach peut indiquer la qualité de l'air et la météo aux points "
                "GPS si tu les fournis dans la conversation."
            )
            tools_used.append("guide_journey_commands")

            # On enrichit avec un état du contexte général
            contexts.append(get_current_air_quality(self._engine))
            tools_used.append("get_current_air_quality")
            return contexts, tools_used

        # general_knowledge : aucun tool, le LLM va devoir préfixer ⚠️
        return [], []

    def _extract_zone(self, question: str) -> str | None:
        """Extrait un nom de zone géographique de la question (heuristique simple)."""
        q = question.lower()
        # On reconnaît quelques zones connues
        zones = [
            "paris", "défense", "defense", "saint-denis", "saint denis",
            "versailles", "créteil", "creteil", "boulogne", "vitry",
            "argenteuil", "cergy", "melun", "aubervilliers",
        ]
        for zone in zones:
            if zone in q:
                return zone
        return None

    def _extract_line(self, question: str) -> str | None:
        """Extrait un nom de ligne court (heuristique sur les patterns connus).

        Reconnaît :
            - RER A, RER B, RER C, RER D, RER E
            - métro 1, métro 14 (codes 1-14)
            - T1, T2, T3a, T3b, T4, T5, T6, T7, T8, T9, T10, T11, T13
            - Bus avec numéros simples (à 2-3 chiffres)
        """
        import re
        q = question.upper()

        # RER
        m = re.search(r"\bRER\s*([A-E])\b", q)
        if m:
            return f"RER {m.group(1)}"

        # Tram T1-T13 et T3a / T3b
        m = re.search(r"\bT\s*([0-9]{1,2}[AB]?)\b", q)
        if m:
            return f"T{m.group(1)}"

        # Métro 1-14 (mots clés métro/metro/ligne)
        m = re.search(r"\b(?:M[ÉE]TRO|METRO|LIGNE)\s*([0-9]{1,2})\b", q)
        if m:
            return m.group(1)

        return None
