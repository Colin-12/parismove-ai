"""Page Trafic — visualisation des passages PRIM IDFM.

Affiche :
    * KPIs en haut (total passages, retard moyen, % de lignes en retard, lignes actives)
    * Top 10 lignes les plus en retard (barchart horizontal)
    * Heatmap heure x jour de la semaine
    * Filtre par mode (Métro / RER / Bus / Tram / Train)
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

import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from dashboard.data import (  # noqa: E402
    format_delay,
    get_available_modes,
    get_top_delayed_lines,
    get_traffic_heatmap,
    get_traffic_kpis,
)
from dashboard.theme import header, page_setup, sidebar_footer  # noqa: E402

DAYS_OF_WEEK = [
    "Dimanche", "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi",
]


def _render_kpis(kpis: dict[str, float | int]) -> None:
    """Affiche la rangée de 4 KPIs en haut de la page."""
    cols = st.columns(4)
    with cols[0]:
        total = int(kpis["total_visits"])
        st.metric("Passages 24h", f"{total:,}".replace(",", " "))
    with cols[1]:
        st.metric("Lignes actives", int(kpis["active_lines"]))
    with cols[2]:
        avg = float(kpis["avg_delay_sec"])
        st.metric("Retard moyen", format_delay(avg))
    with cols[3]:
        pct = float(kpis["pct_late"])
        st.metric(
            "% en retard",
            f"{pct:.1f}%",
            help="Pourcentage de passages avec un retard > 60s",
        )


def _render_top_delays(df: pd.DataFrame) -> None:
    """Affiche le barchart horizontal des lignes les plus en retard."""
    if df.empty:
        st.info("Pas de données de retard sur cette fenêtre.")
        return

    # Calcul du retard en minutes pour l'affichage
    display_df = df.copy()
    display_df["delay_min"] = display_df["avg_delay_sec"] / 60
    display_df["label"] = display_df.apply(
        lambda r: f"{r['line_name']} ({r['transport_mode']})",
        axis=1,
    )

    fig = px.bar(
        display_df.sort_values("delay_min"),
        x="delay_min",
        y="label",
        orientation="h",
        color="delay_min",
        color_continuous_scale=["#10B981", "#F59E0B", "#EF4444"],
        labels={
            "delay_min": "Retard moyen (min)",
            "label": "Ligne",
        },
        hover_data={"visits": True},
    )
    fig.update_layout(
        height=400,
        coloraxis_showscale=False,
        margin={"l": 10, "r": 10, "t": 30, "b": 10},
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_heatmap(df: pd.DataFrame) -> None:
    """Affiche la heatmap heure x jour-de-semaine."""
    if df.empty:
        st.info("Pas assez de données pour générer la heatmap.")
        return

    # Pivote en grille 7 jours x 24 heures
    pivot = (
        df.pivot_table(
            index="day_of_week",
            columns="hour",
            values="avg_delay_sec",
            aggfunc="mean",
        )
        .reindex(index=range(7), columns=range(24))
    )
    # Conversion en minutes pour la lisibilité
    pivot = pivot / 60

    # Étiquettes lisibles
    y_labels = [DAYS_OF_WEEK[i] for i in pivot.index]
    x_labels = [f"{h}h" for h in pivot.columns]

    fig = go.Figure(
        data=go.Heatmap(
            z=pivot.values,
            x=x_labels,
            y=y_labels,
            colorscale=[
                [0.0, "#10B981"],
                [0.5, "#F59E0B"],
                [1.0, "#EF4444"],
            ],
            colorbar={"title": "Retard (min)"},
            hovertemplate=(
                "%{y} %{x}<br>Retard moyen : %{z:.1f} min<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        height=350,
        margin={"l": 10, "r": 10, "t": 30, "b": 10},
        xaxis={"side": "top"},
    )
    st.plotly_chart(fig, use_container_width=True)


def main() -> None:
    page_setup("Trafic", icon="🚇")
    header(
        "🚇 Trafic IDFM",
        "Passages temps-réel des transports en commun franciliens",
    )
    sidebar_footer()

    # --- Filtre mode dans la sidebar ---
    available_modes = get_available_modes()
    with st.sidebar:
        st.markdown("### Filtre")
        mode_filter = st.selectbox(
            "Mode de transport",
            options=["Tous", *available_modes],
            help="Filtre les graphiques par mode (sauf KPIs globaux)",
        )
    selected_mode: str | None = None if mode_filter == "Tous" else mode_filter

    # --- KPIs globaux (toujours sans filtre pour le contexte global) ---
    st.subheader("📊 Vue d'ensemble (24h)")
    kpis = get_traffic_kpis()
    _render_kpis(kpis)

    st.markdown("")  # espace

    # --- Top lignes en retard ---
    label_suffix = f" — {selected_mode}" if selected_mode else ""
    st.subheader(f"🐢 Top 10 lignes les plus en retard{label_suffix}")

    top_df = get_top_delayed_lines(limit=10, mode=selected_mode)
    _render_top_delays(top_df)

    if not top_df.empty:
        with st.expander("Détails du tableau"):
            display = top_df.copy()
            display["Retard moyen"] = display["avg_delay_sec"].apply(format_delay)
            display = display.rename(
                columns={
                    "line_name": "Ligne",
                    "transport_mode": "Mode",
                    "visits": "Nb passages",
                }
            )
            st.dataframe(
                display[["Ligne", "Mode", "Nb passages", "Retard moyen"]],
                use_container_width=True,
                hide_index=True,
            )

    st.markdown("")

    # --- Heatmap ---
    st.subheader(f"🔥 Heatmap des retards par heure et jour{label_suffix}")
    st.caption(
        "Retard moyen (en minutes) sur les 7 derniers jours. "
        "Plus c'est rouge, plus le retard est élevé."
    )

    heatmap_df = get_traffic_heatmap(mode=selected_mode)
    _render_heatmap(heatmap_df)

    # --- Notes méthodologiques ---
    with st.expander("Notes méthodologiques"):
        st.markdown(
            """
            **Source des données** : API PRIM IDFM (Île-de-France Mobilités),
            ingérée toutes les 30 minutes via GitHub Actions.

            **Calcul du retard** : `expected_arrival_at - aimed_arrival_at`
            (différence entre heure prévue temps-réel et heure planifiée).

            **Top 10** : lignes avec au moins 5 passages observés dans les
            24 dernières heures, triées par retard moyen décroissant.

            **Heatmap** : moyenne des retards par tranche horaire sur les
            7 derniers jours. Les cases vides indiquent une absence de
            données (lignes non actives à ce moment).

            **Limitations** : les données ne couvrent que les lignes actives
            au moment de la collecte, et certaines lignes peuvent être
            sous-représentées si leur fréquence est faible.
            """
        )


if __name__ == "__main__":
    main()
