"""Page Qualité de l'air.

Affiche :
    * Une carte Folium avec les stations AQICN colorées selon l'AQI
    * Un tableau récap des dernières mesures par station
    * Un graphique des tendances sur les 48 dernières heures
"""
from __future__ import annotations

import sys
from pathlib import Path

# Path setup (idem app.py)
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

import folium  # noqa: E402
import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402
from streamlit_folium import st_folium  # noqa: E402

from dashboard.data import (  # noqa: E402
    aqi_color,
    aqi_label,
    format_age,
    get_air_history,
    get_latest_air_measurements,
)
from dashboard.theme import (  # noqa: E402
    badge,
    header,
    page_setup,
    sidebar_footer,
)


def _build_map(df: pd.DataFrame) -> folium.Map:
    """Construit une carte Folium centrée sur Paris avec les stations AQICN."""
    # Centre approximatif de l'IDF
    paris_center = [48.8566, 2.3522]
    fmap = folium.Map(
        location=paris_center,
        zoom_start=10,
        tiles="CartoDB positron",  # fond clair, élégant
    )

    for _, row in df.iterrows():
        if pd.isna(row["latitude"]) or pd.isna(row["longitude"]):
            continue

        color = aqi_color(row["aqi"])
        label = aqi_label(row["aqi"])

        popup_html = f"""
        <div style='font-family: sans-serif; min-width: 220px;'>
            <strong style='font-size:1.05rem'>{row['station_name']}</strong><br>
            <span style='color:#6B7280;font-size:0.85rem'>
                Mesuré {format_age(row['measured_at'])}
            </span>
            <hr style='margin:0.5rem 0;'>
            <div style='font-size:0.9rem;'>
                <strong>AQI : {row['aqi'] or '?'}</strong>
                <span style='background:{color};color:white;
                       padding:2px 8px;border-radius:9999px;
                       margin-left:6px;font-size:0.8rem;'>
                    {label}
                </span>
            </div>
            <div style='font-size:0.85rem;margin-top:0.5rem;'>
                {f'PM2.5 : {row["pm25"]:.0f} µg/m³<br>' if pd.notna(row["pm25"]) else ''}
                {f'PM10 : {row["pm10"]:.0f} µg/m³<br>' if pd.notna(row["pm10"]) else ''}
                {f'NO₂ : {row["no2"]:.0f} µg/m³<br>' if pd.notna(row["no2"]) else ''}
                {f'O₃ : {row["o3"]:.0f} µg/m³' if pd.notna(row["o3"]) else ''}
            </div>
        </div>
        """

        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=14,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.75,
            weight=2,
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=row["station_name"],
        ).add_to(fmap)

    return fmap


def main() -> None:
    page_setup("Qualité de l'air", icon="🌫️")
    header(
        "🌫️ Qualité de l'air",
        "Mesures temps réel des stations Airparif via AQICN",
    )
    sidebar_footer()

    # --- Données ---
    df = get_latest_air_measurements()

    if df.empty:
        st.warning(
            "Aucune mesure de qualité de l'air disponible sur les 24 "
            "dernières heures. Le cron a peut-être un souci, ou aucune "
            "station n'est active actuellement."
        )
        return

    # --- KPIs ---
    cols = st.columns(4)
    with cols[0]:
        st.metric("Stations actives", f"{len(df)}")
    with cols[1]:
        avg_aqi = df["aqi"].mean()
        if pd.notna(avg_aqi):
            st.metric("AQI moyen", f"{avg_aqi:.0f}", help=aqi_label(avg_aqi))
        else:
            st.metric("AQI moyen", "?")
    with cols[2]:
        avg_pm25 = df["pm25"].mean()
        if pd.notna(avg_pm25):
            st.metric(
                "PM2.5 moyen",
                f"{avg_pm25:.0f} µg/m³",
                help="Seuil OMS : ≤ 5 µg/m³ idéal",
            )
        else:
            st.metric("PM2.5 moyen", "?")
    with cols[3]:
        latest = df["measured_at"].max()
        st.metric("Dernière mesure", format_age(latest))

    st.markdown("")

    # --- Carte ---
    st.subheader("🗺️ Carte des stations")
    fmap = _build_map(df)
    st_folium(fmap, width=None, height=500, returned_objects=[])

    # --- Tableau récap ---
    st.subheader("📋 Détail par station")

    display_df = df.copy()
    display_df["AQI"] = display_df["aqi"].apply(
        lambda x: f"{int(x)} — {aqi_label(x)}" if pd.notna(x) else "?"
    )
    display_df["PM2.5"] = display_df["pm25"].apply(
        lambda x: f"{x:.0f}" if pd.notna(x) else "—"
    )
    display_df["NO₂"] = display_df["no2"].apply(
        lambda x: f"{x:.0f}" if pd.notna(x) else "—"
    )
    display_df["Mesure"] = display_df["measured_at"].apply(format_age)

    st.dataframe(
        display_df[
            ["station_name", "AQI", "PM2.5", "NO₂", "Mesure", "attribution"]
        ].rename(
            columns={"station_name": "Station", "attribution": "Source"}
        ),
        use_container_width=True,
        hide_index=True,
    )

    # --- Tendances ---
    st.subheader("📈 Évolution sur 48h")

    history = get_air_history(hours=48)
    if history.empty:
        st.info("Pas assez d'historique pour afficher des tendances.")
    else:
        history["measured_at"] = pd.to_datetime(history["measured_at"])
        fig = px.line(
            history,
            x="measured_at",
            y="aqi",
            color="station_name",
            title="AQI par station sur les 48 dernières heures",
            labels={
                "measured_at": "Date",
                "aqi": "AQI",
                "station_name": "Station",
            },
        )
        fig.update_layout(
            hovermode="x unified",
            height=400,
            legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
        )
        st.plotly_chart(fig, use_container_width=True)

    # --- Aide à l'interprétation ---
    with st.expander("Comprendre l'AQI et les seuils OMS"):
        st.markdown(
            f"""
            #### Air Quality Index (AQI)
            L'**AQI** est un indicateur synthétique de qualité de l'air entre
            0 et 500 où plus c'est bas, mieux c'est.

            | Plage | Catégorie | Risque |
            |-------|-----------|--------|
            | 0-50  | {badge('Bon', '#10B981')} | Aucun |
            | 51-100  | {badge('Modéré', '#F59E0B')} | Personnes très sensibles |
            | 101-150 | {badge('Mauvais (sensibles)', '#F97316')} | Sensibles à risque |
            | 151-200 | {badge('Mauvais', '#EF4444')} | Tout le monde |
            | 201-300 | {badge('Très mauvais', '#A855F7')} | Sérieux |
            | 301+ | {badge('Dangereux', '#7C2D12')} | Urgence sanitaire |

            #### Seuils OMS 2021 (PM2.5)
            - **≤ 5 µg/m³** sur 24h : recommandé long terme
            - **15 µg/m³** : limite haute "acceptable"
            - **25 µg/m³** : alerte sanitaire
            - **50+ µg/m³** : danger immédiat

            *Sources : World Health Organization, US EPA AirNow.*
            """,
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
