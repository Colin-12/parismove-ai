"""Page Prévision air — Visualise les prédictions PM2.5 du modèle ML.

Affiche :
    * KPIs du modèle (date d'entraînement, MAE, RMSE)
    * Sélecteur de station Airparif
    * Prédiction H+1 pour la station choisie
    * Graphique 3 traces (réalité, backtest, prédiction future)

Si le modèle n'est pas encore entraîné, on affiche un message guidant
l'utilisateur (en local) ou une note "modèle indisponible" (en prod).
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import TypedDict

# Path setup pour Streamlit Cloud
THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = THIS_DIR.parent.parent.parent.parent.parent
SRC_PATHS = [
    PROJECT_ROOT / "shared" / "src",
    PROJECT_ROOT / "services" / "ingestion" / "src",
    PROJECT_ROOT / "services" / "healthscore" / "src",
    PROJECT_ROOT / "services" / "coach" / "src",
    PROJECT_ROOT / "services" / "ml-pollution" / "src",
    PROJECT_ROOT / "services" / "dashboard" / "src",
]
for src_path in SRC_PATHS:
    if src_path.exists() and str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402
from ml_pollution.config import get_model_dir  # noqa: E402
from ml_pollution.persistence import load_model, model_exists  # noqa: E402
from ml_pollution.predict import (  # noqa: E402
    backtest_station,
    predict_next_hour,
)

from dashboard.data import (  # noqa: E402
    aqi_color,
    format_age,
    get_engine,
    get_latest_air_measurements,
)
from dashboard.theme import header, page_setup, sidebar_footer  # noqa: E402


class PredictionDict(TypedDict):
    """Type structuré pour le résultat de _cached_predict."""

    station_id: str
    station_name: str
    target_dt: datetime
    predicted_pm25: float
    last_observed_pm25: float
    last_observed_at: datetime


@st.cache_data(ttl=300)
def _cached_predict(station_id: str) -> PredictionDict | None:
    """Cache la prédiction pour éviter de réentraîner à chaque rerun."""
    engine = get_engine()
    model_dir = get_model_dir()
    try:
        pred = predict_next_hour(engine, model_dir, station_id)
    except (FileNotFoundError, ValueError):
        return None

    return {
        "station_id": pred.station_id,
        "station_name": pred.station_name,
        "target_dt": pred.target_dt,
        "predicted_pm25": pred.predicted_pm25,
        "last_observed_pm25": pred.last_observed_pm25,
        "last_observed_at": pred.last_observed_at,
    }


@st.cache_data(ttl=600)
def _cached_backtest(station_id: str, hours: int = 48) -> pd.DataFrame:
    engine = get_engine()
    model_dir = get_model_dir()
    try:
        return backtest_station(engine, model_dir, station_id, hours=hours)
    except (FileNotFoundError, ValueError):
        return pd.DataFrame(
            columns=["measured_at", "pm25_real", "pm25_predicted"]
        )


def _render_no_model_message() -> None:
    """Affiche un message clair quand aucun modèle n'est disponible."""
    st.warning(
        "Aucun modèle de prédiction n'est encore disponible. "
        "Le service `ml-pollution` doit être entraîné au moins une fois."
    )
    with st.expander("Comment entraîner le modèle ?"):
        st.markdown(
            """
            En local, depuis la racine du projet :

            ```bash
            pip install -e services/ml-pollution
            ml-pollution train --days 30
            ```

            Le modèle sera sauvegardé dans `services/ml-pollution/models/`
            puis automatiquement utilisé par cette page.

            **Note** : il faut au moins ~30 mesures par station pour que
            l'entraînement réussisse (les lag features H-1 et H-24 nécessitent
            au moins 24h+ d'historique continu).
            """
        )


def main() -> None:
    page_setup("Prévision air", icon="🔮")
    header(
        "🔮 Prévision qualité de l'air",
        "Modèle XGBoost pour prédire la concentration PM2.5 à H+1",
    )
    sidebar_footer()

    model_dir = get_model_dir()
    if not model_exists(model_dir):
        _render_no_model_message()
        return

    # --- Métadonnées du modèle (en haut) ---
    try:
        _model, metadata = load_model(model_dir)
    except FileNotFoundError:
        _render_no_model_message()
        return

    metrics = metadata.get("metrics", {})
    cols = st.columns(4)
    with cols[0]:
        st.metric(
            "MAE", f"{metrics.get('mae', 0):.2f} µg/m³",
            help="Erreur Absolue Moyenne sur le set de test",
        )
    with cols[1]:
        st.metric(
            "RMSE", f"{metrics.get('rmse', 0):.2f} µg/m³",
            help="Racine de l'Erreur Quadratique Moyenne",
        )
    with cols[2]:
        st.metric("Échantillons train", f"{metrics.get('n_train', 0)}")
    with cols[3]:
        saved_at = metadata.get("saved_at", "?")
        if saved_at and saved_at != "?":
            saved_dt = pd.Timestamp(saved_at)
            st.metric("Entraîné", format_age(saved_dt.to_pydatetime()))
        else:
            st.metric("Entraîné", "?")

    st.markdown("")

    # --- Sélecteur de station ---
    air_df = get_latest_air_measurements()
    if air_df.empty:
        st.info("Aucune station Airparif active actuellement.")
        return

    station_options = dict(
        zip(air_df["station_id"], air_df["station_name"], strict=False)
    )

    selected_id = st.selectbox(
        "Choisis une station Airparif",
        options=list(station_options.keys()),
        format_func=lambda x: f"{station_options[x]} ({x})",
    )

    if not selected_id:
        return

    # --- Prédiction H+1 ---
    pred = _cached_predict(selected_id)
    if pred is None:
        st.warning(
            "Pas assez d'historique pour prédire sur cette station "
            "(il faut au moins 24h de mesures continues)."
        )
        return

    color = aqi_color(pred["predicted_pm25"])
    target_dt_str = pd.Timestamp(pred["target_dt"]).strftime("%H:%M")

    st.markdown(
        f"""
        <div style='
            background: {color};
            padding: 1.25rem;
            border-radius: 0.5rem;
            color: white;
            text-align: center;
            margin: 1rem 0;
        '>
            <div style='font-size: 0.85rem; opacity: 0.9;
                        text-transform: uppercase; letter-spacing: 0.1em;'>
                Prédiction PM2.5 pour {target_dt_str}
            </div>
            <div style='font-size: 2.5rem; font-weight: 700; margin: 0.25rem 0;'>
                {pred['predicted_pm25']:.1f} µg/m³
            </div>
            <div style='font-size: 0.95rem; font-weight: 500;'>
                Dernière mesure : {pred['last_observed_pm25']:.1f} µg/m³
                ({format_age(pd.Timestamp(pred['last_observed_at']).to_pydatetime())})
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --- Graphique avec 3 traces (inspiré OptiMobility) ---
    st.subheader("Évolution et prédictions")

    backtest_df = _cached_backtest(selected_id, hours=48)
    real_df = air_df[air_df["station_id"] == selected_id]

    fig = go.Figure()

    # Trace 1 : réalité historique
    if not real_df.empty:
        fig.add_trace(go.Scatter(
            x=real_df["measured_at"],
            y=real_df["pm25"],
            mode="lines+markers",
            name="Réalité observée",
            line={"color": "#0EA5E9", "width": 2},
        ))

    # Trace 2 : prédictions passées (backtest)
    if not backtest_df.empty:
        fig.add_trace(go.Scatter(
            x=backtest_df["measured_at"],
            y=backtest_df["pm25_predicted"],
            mode="lines",
            name="Prédiction passée (backtest)",
            line={"color": "#10B981", "dash": "dot", "width": 2},
        ))

    # Trace 3 : prédiction future
    fig.add_trace(go.Scatter(
        x=[pred["last_observed_at"], pred["target_dt"]],
        y=[pred["last_observed_pm25"], pred["predicted_pm25"]],
        mode="lines+markers",
        name="Prédiction future (H+1)",
        line={"color": "#EF4444", "dash": "dash", "width": 3},
        marker={"size": 10},
    ))

    fig.update_layout(
        xaxis_title="Heure",
        yaxis_title="PM2.5 (µg/m³)",
        hovermode="x unified",
        height=420,
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "x": 0,
        },
    )
    st.plotly_chart(fig, use_container_width=True)

    # --- Notes méthodologiques ---
    with st.expander("Comment fonctionne le modèle ?"):
        st.markdown(
            f"""
            ### Algorithme
            **XGBoost Regressor** (gradient boosting sur arbres) entraîné
            sur les données AQICN/Airparif et Open-Meteo des
            {metadata.get('data_window_days', '?')} derniers jours.

            ### Features utilisées
            | Catégorie | Features |
            |-----------|----------|
            | Temporelles | `heure`, `jour_semaine`, `mois` |
            | Lag (PM2.5) | `pm25_h1` (il y a 1h), `pm25_h24` (il y a 24h) |
            | Météo | `temperature_c`, `humidity_pct`, `wind_speed_ms`, `precipitation_mm` |
            | Géographique | `station_id` (catégoriel) |

            ### Architecture
            **Modèle global** avec station_id comme feature catégorielle
            (encodée nativement par XGBoost via `enable_categorical=True`).
            Permet de tirer parti du volume total de mesures tout en
            laissant le modèle apprendre les spécificités de chaque
            station.

            ### Validation
            Split **chronologique** (pas aléatoire) pour éviter la fuite
            temporelle : les 20% les plus récents forment le set de test.

            ### Limites
            - **Fenêtre courte** : avec 6 jours de data, les patterns
              hebdomadaires et saisonniers ne sont pas bien capturés.
            - **Pas de variables exogènes** : émissions industrielles,
              jours fériés, événements parisiens ne sont pas pris en compte.
            - **Horizon court** : le modèle ne prédit qu'à H+1. Pour des
              prévisions multi-heures, il faudrait un modèle plus complexe
              (LSTM, Prophet, ARIMA).
            """
        )


if __name__ == "__main__":
    main()
