"""Page Score santé — Calculateur interactif de trajet.

Affiche :
    * Sélecteur de zones prédéfinies (départ + arrivée)
    * Bouton "Calculer"
    * Affichage du grade A-E + sub-scores (Pollution / Météo / Trafic)
    * Carte Folium avec marqueurs trajet et stations Airparif proches
    * Conseil actionnable basé sur le grade
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

import folium  # noqa: E402
import streamlit as st  # noqa: E402
from healthscore.compare import score_journey  # noqa: E402
from streamlit_folium import st_folium  # noqa: E402

from dashboard.data import (  # noqa: E402
    PREDEFINED_ZONES,
    aqi_color,
    get_engine,
    get_latest_air_measurements,
    grade_color,
)
from dashboard.theme import header, page_setup, sidebar_footer  # noqa: E402

# Conseils par grade pour aider l'utilisateur à interpréter
ADVICE_BY_GRADE = {
    "A": "🟢 Excellent trajet ! Conditions optimales pour la santé.",
    "B": "🟢 Bon trajet, peu de risques pour la santé.",
    "C": "🟡 Trajet correct, prévoyez un peu plus de temps.",
    "D": "🟠 Conditions dégradées : si vous êtes sensible (asthme, "
         "enfants, personnes âgées), envisagez un autre itinéraire.",
    "E": "🔴 Trajet à éviter si possible. Conditions difficiles "
         "(pollution forte, gros retards, météo hostile).",
}


def _build_journey_map(
    start_label: str,
    start_coords: tuple[float, float],
    end_label: str,
    end_coords: tuple[float, float],
) -> folium.Map:
    """Construit la carte du trajet avec marqueurs + stations Airparif proches."""
    # Centre = milieu du trajet
    center_lat = (start_coords[0] + end_coords[0]) / 2
    center_lon = (start_coords[1] + end_coords[1]) / 2

    fmap = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=11,
        tiles="CartoDB positron",
    )

    # Marqueur départ
    folium.Marker(
        location=list(start_coords),
        popup=folium.Popup(f"<strong>Départ :</strong> {start_label}", max_width=250),
        tooltip=f"Départ : {start_label}",
        icon=folium.Icon(color="green", icon="play", prefix="fa"),
    ).add_to(fmap)

    # Marqueur arrivée
    folium.Marker(
        location=list(end_coords),
        popup=folium.Popup(f"<strong>Arrivée :</strong> {end_label}", max_width=250),
        tooltip=f"Arrivée : {end_label}",
        icon=folium.Icon(color="red", icon="flag", prefix="fa"),
    ).add_to(fmap)

    # Ligne du trajet (à vol d'oiseau, c'est volontaire — on ne fait pas
    # de routage type Citymapper, c'est une indication visuelle)
    folium.PolyLine(  # type: ignore[no-untyped-call]
        locations=[start_coords, end_coords],
        color="#0EA5E9",
        weight=4,
        opacity=0.7,
        dash_array="10",
    ).add_to(fmap)

    # Stations Airparif les plus proches (cercles colorés)
    air_df = get_latest_air_measurements()
    if not air_df.empty:
        for _, row in air_df.iterrows():
            if row.get("latitude") is None or row.get("longitude") is None:
                continue
            color = aqi_color(row["aqi"])
            popup_html = (
                f"<strong>{row['station_name']}</strong><br>"
                f"AQI : {row['aqi'] or '?'}<br>"
                f"<small>{row.get('attribution', '')}</small>"
            )
            folium.CircleMarker(
                location=[row["latitude"], row["longitude"]],
                radius=8,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.6,
                weight=1,
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=f"Station {row['station_name']}",
            ).add_to(fmap)

    return fmap


def _render_score_results(
    journey_id: str,
    label: str,
    waypoints: list[tuple[float, float]],
) -> None:
    """Calcule et affiche le score santé du trajet."""
    engine = get_engine()

    with st.spinner("Calcul du score..."):
        try:
            result = score_journey(
                engine=engine,
                journey_id=journey_id,
                journey_label=label,
                waypoints=waypoints,
            )
        except Exception as exc:
            st.error(f"Erreur lors du calcul : {exc}")
            return

    # Le grade est un enum HealthGrade — on prend sa valeur string
    grade = result.grade.value if hasattr(result.grade, "value") else str(result.grade)
    color = grade_color(grade)

    # En-tête grade + score global en gros
    st.markdown(
        f"""
        <div style='
            background: {color};
            padding: 1.5rem;
            border-radius: 0.5rem;
            color: white;
            text-align: center;
            margin-bottom: 1rem;
        '>
            <div style='font-size: 0.9rem; opacity: 0.9;
                        text-transform: uppercase; letter-spacing: 0.1em;'>
                Score santé
            </div>
            <div style='font-size: 3rem; font-weight: 700; margin: 0.25rem 0;'>
                Grade {grade}
            </div>
            <div style='font-size: 1.25rem; font-weight: 500;'>
                {result.overall_score:.1f} / 100
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Sub-scores en 3 colonnes
    cols = st.columns(3)
    with cols[0]:
        st.metric(
            "🌫️ Pollution",
            f"{result.pollution_score:.0f}/100",
            help="Score basé sur les mesures Airparif des stations proches",
        )
    with cols[1]:
        st.metric(
            "🌤️ Météo",
            f"{result.weather_score:.0f}/100",
            help="Score basé sur la température, humidité, pluie et vent",
        )
    with cols[2]:
        st.metric(
            "🚇 Trafic",
            f"{result.traffic_score:.0f}/100",
            help="Score basé sur les retards récents des lignes alentour",
        )

    # Conseil actionnable
    advice = ADVICE_BY_GRADE.get(grade, "")
    if advice:
        st.info(advice)

    # Avertissements
    if result.warnings:
        with st.expander(f"⚠️ {len(result.warnings)} avertissement(s)"):
            for warning in result.warnings:
                st.markdown(f"- {warning}")


def main() -> None:
    page_setup("Score santé", icon="🌿")
    header(
        "🌿 Score santé d'un trajet",
        "Évalue la qualité d'un trajet selon la pollution, la météo et le trafic",
    )
    sidebar_footer()

    # --- Sélecteurs ---
    st.markdown("### Choisis ton trajet")

    zone_names = list(PREDEFINED_ZONES.keys())

    cols = st.columns(2)
    with cols[0]:
        start_label = st.selectbox(
            "🟢 Départ",
            options=zone_names,
            index=0,
            key="start_zone",
        )
    with cols[1]:
        end_label = st.selectbox(
            "🔴 Arrivée",
            options=zone_names,
            index=1,
            key="end_zone",
        )

    if start_label == end_label:
        st.warning(
            "Le départ et l'arrivée sont identiques — choisis 2 zones différentes."
        )
        return

    start_coords = PREDEFINED_ZONES[start_label]
    end_coords = PREDEFINED_ZONES[end_label]

    if st.button("📊 Calculer le score santé", type="primary", use_container_width=True):
        st.session_state["journey_calculated"] = True
        st.session_state["journey_data"] = {
            "start_label": start_label,
            "start_coords": start_coords,
            "end_label": end_label,
            "end_coords": end_coords,
        }

    # --- Affichage des résultats si calcul fait ---
    if st.session_state.get("journey_calculated"):
        data = st.session_state["journey_data"]

        st.markdown("---")
        st.markdown(
            f"### Trajet : {data['start_label']} → {data['end_label']}"
        )

        # Résultats du score
        _render_score_results(
            journey_id=f"{data['start_label']}-{data['end_label']}".lower().replace(
                " ", "-"
            ),
            label=f"{data['start_label']} → {data['end_label']}",
            waypoints=[data["start_coords"], data["end_coords"]],
        )

        # Carte
        st.markdown("### 🗺️ Carte du trajet")
        st.caption(
            "Le tracé est en pointillés (à vol d'oiseau). Les cercles colorés "
            "montrent les stations Airparif proches avec leur qualité d'air actuelle."
        )

        fmap = _build_journey_map(
            start_label=data["start_label"],
            start_coords=data["start_coords"],
            end_label=data["end_label"],
            end_coords=data["end_coords"],
        )
        st_folium(fmap, width=None, height=500, returned_objects=[])

    # --- Aide à l'interprétation ---
    with st.expander("Comment est calculé le score santé ?"):
        st.markdown(
            """
            Le score santé est une note **A à E** combinant 3 dimensions :

            | Dimension | Poids | Source |
            |-----------|-------|--------|
            | 🌫️ Pollution | 60% | AQICN / Airparif (stations à <5 km) |
            | 🌤️ Météo | 30% | Open-Meteo (point le plus proche) |
            | 🚇 Trafic | 10% | PRIM IDFM (lignes traversées) |

            #### Échelle des grades
            - **A (90-100)** : Conditions optimales
            - **B (75-90)** : Bonnes conditions
            - **C (60-75)** : Conditions correctes
            - **D (40-60)** : Conditions dégradées
            - **E (0-40)** : Conditions difficiles

            #### À noter
            Le tracé est en **vol d'oiseau** : nous ne calculons pas
            d'itinéraire optimal. Pour un vrai routage multimodal type
            Citymapper, il faudrait intégrer l'API IDFM journey-planner
            (prévu dans une future PR).
            """
        )


if __name__ == "__main__":
    main()
