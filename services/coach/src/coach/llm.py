"""Client LLM (Groq) abstrait pour le coach.

Wrapper minimaliste qui :
    * Encapsule l'appel Groq dans une interface simple
    * Permet le mock dans les tests
    * Gère les paramètres factuels (température basse, max tokens)
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from groq import Groq


class ChatMessage(Protocol):
    """Format minimal d'un message (compatible OpenAI / Groq)."""

    role: str
    content: str


class LLMClient:
    """Client minimaliste pour Groq (compatible API OpenAI).

    Le client est initialisé une fois et réutilisé sur toute la session.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 800,
    ) -> None:
        if not api_key:
            raise ValueError("Une clé API Groq est requise")
        self._client = Groq(api_key=api_key)
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    def chat(
        self,
        messages: Iterable[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Envoie une conversation au LLM et retourne sa réponse texte.

        Args:
            messages: liste de {"role": "system|user|assistant", "content": "..."}
            model: surcharge le modèle par défaut (ex: passer au modèle léger
                   pour les tâches simples)
            temperature: surcharge la température
            max_tokens: surcharge la longueur max

        Returns:
            La réponse du LLM en texte brut.
        """
        response = self._client.chat.completions.create(
            model=model or self._model,
            messages=list(messages),  # type: ignore[arg-type]
            temperature=temperature if temperature is not None else self._temperature,
            max_tokens=max_tokens or self._max_tokens,
        )
        content = response.choices[0].message.content
        return content or ""
