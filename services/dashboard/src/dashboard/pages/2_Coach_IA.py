"""Page Coach IA — Chat conversationnel data-aware.

Réutilise 100% du service `coach` (Coach orchestrator + tools) pour
répondre aux questions des utilisateurs en langage naturel.

UX :
    * 3-4 suggestions cliquables au démarrage
    * Chat avec st.chat_message et st.chat_input
    * Pas de mémoire entre messages (chaque question est indépendante)
    * Expander "Détails techniques" pour voir intent + tools utilisés
    * Bouton "Nouvelle conversation" dans la sidebar
"""
from __future__ import annotations

import sys
from pathlib import Path

# Path setup pour Streamlit Cloud
THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = THIS_DIR.parent.parent.parent.parent.parent
SRC_PATHS = [
    PROJECT_ROOT / "shared" / "src",
    PROJECT_ROOT / "services" / "ingestion" / "src",
    PROJECT_ROOT / "services" / "healthscore" / "src",
    PROJECT_ROOT / "services" / "coach" / "src",
    PROJECT_ROOT / "services" / "dashboard" / "src",
]
for src_path in SRC_PATHS:
    if src_path.exists() and str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

import streamlit as st  # noqa: E402
from coach.llm import LLMClient  # noqa: E402
from coach.orchestrator import Coach, CoachResponse  # noqa: E402

from dashboard.config import get_settings  # noqa: E402
from dashboard.data import get_engine  # noqa: E402
from dashboard.theme import header, page_setup, sidebar_footer  # noqa: E402

# Suggestions de questions affichées au démarrage.
# Volontairement variées pour montrer les capacités du coach.
SUGGESTIONS = [
    ("💨", "Comment est l'air à Paris en ce moment ?"),
    ("🚇", "Comment se passe le trafic des transports ?"),
    ("🌤️", "Quel temps fait-il à La Défense ?"),
    ("?", "Que sais-tu faire ?"),
]


@st.cache_resource
def get_coach() -> Coach:
    """Instancie le Coach (mise en cache au niveau session)."""
    settings = get_settings()
    if not settings.groq_api_key:
        st.error(
            "❌ GROQ_API_KEY n'est pas configurée. "
            "Le coach ne peut pas fonctionner."
        )
        st.stop()

    engine = get_engine()
    llm = LLMClient(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        temperature=0.3,
        max_tokens=800,
    )
    return Coach(engine=engine, llm=llm, small_model=settings.groq_model_small)


def _ask_and_render(question: str) -> None:
    """Pose la question au coach et rend la réponse dans le chat."""
    coach = get_coach()

    # Affiche immédiatement la question utilisateur
    with st.chat_message("user", avatar="🙋"):
        st.markdown(question)

    # Affiche la réponse en mode "réflexion" puis la complète
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Réflexion en cours..."):
            try:
                response: CoachResponse = coach.ask(question)
            except Exception as exc:
                st.error(f"Erreur : {exc}")
                return

        st.markdown(response.answer)

        # Détails techniques (caché par défaut)
        with st.expander("Détails techniques"):
            cols = st.columns(3)
            with cols[0]:
                st.metric("Intent détecté", response.intent.value)
            with cols[1]:
                st.metric("Langue", response.language.upper())
            with cols[2]:
                st.metric(
                    "Données temps-réel",
                    "Oui ✅" if response.has_real_data else "Non ⚠️",
                )

            if response.tools_used:
                st.markdown(
                    "**Tools utilisés :** "
                    + ", ".join(f"`{t}`" for t in response.tools_used)
                )
            else:
                st.markdown("**Tools utilisés :** aucun (knowledge générale)")


def _render_suggestions() -> str | None:
    """Affiche les suggestions cliquables. Retourne la question choisie ou None."""
    st.markdown("##### Quelques suggestions pour démarrer :")

    cols = st.columns(len(SUGGESTIONS))
    for col, (emoji, question) in zip(cols, SUGGESTIONS, strict=True):
        with col:
            # Le label du bouton inclut l'emoji + un extrait court
            short_label = f"{emoji} {question[:40]}"
            if len(question) > 40:
                short_label += "..."
            if st.button(short_label, key=f"suggest_{question}", use_container_width=True):
                return question
    return None


def main() -> None:
    page_setup("Coach IA", icon="🤖")
    header(
        "🤖 Coach IA",
        "Pose tes questions sur la mobilité francilienne en langage naturel",
    )
    sidebar_footer()

    # Bouton nouvelle conversation dans la sidebar
    with st.sidebar:
        if st.button("🔄 Nouvelle conversation", use_container_width=True):
            st.session_state.pop("chat_history", None)
            st.rerun()

    # Initialisation de l'historique en session_state
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Rendu de l'historique précédent
    for entry in st.session_state.chat_history:
        with st.chat_message(entry["role"], avatar=entry["avatar"]):
            st.markdown(entry["content"])
            if entry.get("metadata"):
                with st.expander("Détails techniques"):
                    meta = entry["metadata"]
                    cols = st.columns(3)
                    with cols[0]:
                        st.metric("Intent détecté", meta["intent"])
                    with cols[1]:
                        st.metric("Langue", meta["language"].upper())
                    with cols[2]:
                        st.metric(
                            "Données temps-réel",
                            "Oui ✅" if meta["has_real_data"] else "Non ⚠️",
                        )
                    if meta["tools_used"]:
                        st.markdown(
                            "**Tools utilisés :** "
                            + ", ".join(f"`{t}`" for t in meta["tools_used"])
                        )
                    else:
                        st.markdown("**Tools utilisés :** aucun")

    # Suggestions affichées seulement si la conversation est vide
    user_question: str | None = None
    if not st.session_state.chat_history:
        user_question = _render_suggestions()
        st.markdown("")  # espace
        st.info(
            "💡 Le coach utilise des **données temps-réel** (Airparif, "
            "Open-Meteo, PRIM IDFM) pour répondre. "
            "Quand il n'a pas la donnée, il le signale clairement avec ⚠️."
        )

    # Champ de saisie principal
    typed_question = st.chat_input("Pose ta question…")

    # Question soit cliquée soit tapée
    final_question = user_question or typed_question

    if final_question:
        # Ajoute la question utilisateur à l'historique
        st.session_state.chat_history.append({
            "role": "user",
            "avatar": "🙋",
            "content": final_question,
        })

        # Appel du coach et stockage de la réponse
        coach = get_coach()
        try:
            with st.spinner("Réflexion en cours..."):
                response = coach.ask(final_question)

            st.session_state.chat_history.append({
                "role": "assistant",
                "avatar": "🤖",
                "content": response.answer,
                "metadata": {
                    "intent": response.intent.value,
                    "language": response.language,
                    "has_real_data": response.has_real_data,
                    "tools_used": response.tools_used,
                },
            })
        except Exception as exc:
            st.session_state.chat_history.append({
                "role": "assistant",
                "avatar": "🤖",
                "content": f"❌ Erreur : {exc}",
            })

        # Rerun pour afficher la nouvelle conversation depuis l'historique
        st.rerun()


if __name__ == "__main__":
    main()
