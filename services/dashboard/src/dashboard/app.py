"""Page d'accueil du dashboard ParisMove AI.

Affiche une vue d'ensemble du système :
    * KPIs globaux (mesures collectées, sources actives, dernière ingestion)
    * Historique récent de l'ingestion (volume par source par heure)
    * Liens rapides vers les autres pages

Lancement local :
    streamlit run services/dashboard/src/dashboard/app.py

Sur Streamlit Cloud :
    Entry point = services/dashboard/src/dashboard/app.py
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import cast

# Ajout des répertoires src/ au PYTHONPATH si lancé via `streamlit run`
# (les `pip install -e` ne sont pas systématiques sur Streamlit Cloud)
THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = THIS_DIR.parent.parent.parent.parent
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

import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402

from dashboard.data import (  # noqa: E402
    format_age,
    get_global_stats,
    get_ingestion_history,
)
from dashboard.theme import header, kpi_card, page_setup, sidebar_footer  # noqa: E402


def main() -> None:
    page_setup("Accueil", icon="🏠")
    header(
        "🚇 ParisMove AI",
        "Tableau de bord temps réel de la mobilité francilienne",
    )
    sidebar_footer()

    # --- KPIs globaux ---
    stats = get_global_stats()

    cols = st.columns(4)
    with cols[0]:
        kpi_card(
            "Passages PRIM",
            f"{stats['stop_visits_count']:,}".replace(",", " "),
            f"Dernier {format_age(cast(datetime | None, stats['last_stop_visit']))}",
        )
    with cols[1]:
        kpi_card(
            "Mesures Air",
            f"{stats['air_count']:,}".replace(",", " "),
            f"Dernière {format_age(cast(datetime | None, stats['last_air']))}",
        )
    with cols[2]:
        kpi_card(
            "Observations Météo",
            f"{stats['weather_count']:,}".replace(",", " "),
            f"Dernière {format_age(cast(datetime | None, stats['last_weather']))}",
        )
    with cols[3]:
        kpi_card(
            "Lignes IDFM",
            f"{stats['lines_count']:,}".replace(",", " "),
            "Référentiel statique",
        )

    st.markdown("")  # espace

    # --- Ingestion sur les dernières 24h ---
    st.subheader("📥 Ingestion sur les 24 dernières heures")

    df = get_ingestion_history(hours=24)
    if df.empty:
        st.info("Pas encore de données ingérées sur cette fenêtre.")
    else:
        # Pivot pour faire un graphe area avec une couleur par source
        df["hour"] = pd.to_datetime(df["hour"])
        fig = px.area(
            df,
            x="hour",
            y="count",
            color="source",
            title="Volume de données collectées par heure et par source",
            color_discrete_map={
                "PRIM IDFM": "#0EA5E9",
                "AQICN": "#10B981",
                "Open-Meteo": "#F59E0B",
            },
            labels={"hour": "Heure", "count": "Nombre d'enregistrements", "source": "Source"},
        )
        fig.update_layout(
            hovermode="x unified",
            height=380,
            legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
        )
        st.plotly_chart(fig, use_container_width=True)

    # --- À propos ---
    with st.expander(" À propos de ce projet"):
        st.markdown(
            """
            **ParisMove AI** est un projet étudiant de fin d'études (Mastère 2
            Big Data & IA, Sup de Vinci) qui démontre une stack data
            engineering complète sur des données ouvertes franciliennes.

            #### Sources
            - **PRIM IDFM** : passages temps réel des transports en commun
            - **AQICN / Airparif** : mesures officielles de qualité de l'air
            - **Open-Meteo** : prévisions météo et qualité air modélisée
            - **IDFM Référentiel** : 2 100+ lignes de transport référencées

            #### Stack technique
            Python · PostgreSQL (Supabase) · GitHub Actions · Streamlit · Groq (LLaMA)

            #### Architecture
            5 services autonomes : `ingestion` (écrivain), `healthscore` (scoring),
            `coach` (assistant IA), `dashboard` (visualisation), `shared`
            (modèles communs).
            """
        )


if __name__ == "__main__":
    main()
