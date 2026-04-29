"""Classification d'intent : que veut l'utilisateur ?

Plutôt que d'utiliser un LLM 70B pour une tâche simple, on emploie le modèle
8B (10x plus rapide, gratuit) avec un prompt structuré qui force une sortie
JSON parsable.

Catégories supportées :
    * greeting          : "salut", "bonjour"
    * help              : "qu'est-ce que tu sais faire ?"
    * air_quality       : questions sur la pollution
    * weather           : questions sur la météo
    * traffic           : questions sur les transports / retards
    * journey_score     : "score santé d'un trajet"
    * journey_compare   : "compare A vs B"
    * general_knowledge : tout le reste (doit déclencher le warning ⚠️)
"""
from __future__ import annotations

import json
import logging
from enum import StrEnum

from coach.llm import LLMClient

logger = logging.getLogger(__name__)


class IntentType(StrEnum):
    GREETING = "greeting"
    HELP = "help"
    AIR_QUALITY = "air_quality"
    WEATHER = "weather"
    TRAFFIC = "traffic"
    JOURNEY_SCORE = "journey_score"
    JOURNEY_COMPARE = "journey_compare"
    GENERAL_KNOWLEDGE = "general_knowledge"


_INTENT_PROMPT = """Tu es un classifieur d'intentions pour un assistant mobilité parisien.

Catégories disponibles :
- greeting : salutations simples ("salut", "bonjour", "hello")
- help : demande d'aide ("que sais-tu faire ?", "à quoi tu sers ?")
- air_quality : pollution, qualité de l'air, PM2.5, NO2 ("quel air il y a ?")
- weather : météo, température, pluie, vent ("il pleut ?", "il fait chaud ?")
- traffic : transports, retards, lignes, arrêts ("comment est le RER A ?")
- journey_score : score santé/qualité d'un trajet unique
- journey_compare : comparer plusieurs trajets ("vaut mieux RER A ou métro 1 ?")
- general_knowledge : tout le reste (questions générales, hors sujet, philosophiques)

Réponds STRICTEMENT en JSON valide, sans markdown, sans texte additionnel :
{"intent": "<catégorie>", "language": "fr|en"}

Exemples :
"salut" → {"intent": "greeting", "language": "fr"}
"hello there" → {"intent": "greeting", "language": "en"}
"compare le RER A et le métro 1" → {"intent": "journey_compare", "language": "fr"}
"is it raining in Paris?" → {"intent": "weather", "language": "en"}
"qui est président de la France ?" → {"intent": "general_knowledge", "language": "fr"}
"""


class IntentResult:
    """Résultat de la classification."""

    def __init__(self, intent: IntentType, language: str) -> None:
        self.intent = intent
        self.language = language

    def __repr__(self) -> str:
        return f"IntentResult(intent={self.intent.value}, language={self.language})"


def classify_intent(question: str, llm: LLMClient, model: str | None = None) -> IntentResult:
    """Classifie une question en (intent, langue).

    En cas d'erreur de parsing JSON, fallback sur GENERAL_KNOWLEDGE en français.

    Args:
        question: la question utilisateur
        llm: le client LLM
        model: surcharge optionnelle (ex: utiliser le modèle léger 8B)
    """
    try:
        response = llm.chat(
            messages=[
                {"role": "system", "content": _INTENT_PROMPT},
                {"role": "user", "content": question},
            ],
            model=model,
            temperature=0.0,  # totalement déterministe pour la classification
            max_tokens=80,
        )
        # Le LLM peut parfois entourer la sortie de markdown malgré l'instruction
        cleaned = response.strip().lstrip("`").rstrip("`")
        if cleaned.startswith("json\n"):
            cleaned = cleaned[5:]
        data = json.loads(cleaned)

        intent_str = data.get("intent", "general_knowledge")
        language = data.get("language", "fr")
        if language not in ("fr", "en"):
            language = "fr"
        try:
            intent = IntentType(intent_str)
        except ValueError:
            intent = IntentType.GENERAL_KNOWLEDGE
        return IntentResult(intent, language)
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        logger.warning(
            "intent_classification_failed",
            extra={"error": str(exc), "question": question[:100]},
        )
        return IntentResult(IntentType.GENERAL_KNOWLEDGE, "fr")
