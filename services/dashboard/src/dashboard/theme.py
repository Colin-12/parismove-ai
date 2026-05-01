"""Helpers UI partagés entre toutes les pages.

Inclut :
    * Configuration de la page Streamlit (titre, layout, sidebar)
    * Header avec branding ParisMove AI
    * CSS custom pour un look pro
"""
from __future__ import annotations

from typing import Literal

import streamlit as st

# Identité visuelle ParisMove AI
COLOR_PRIMARY = "#0EA5E9"      # bleu IDF
COLOR_SECONDARY = "#10B981"    # vert (santé)
COLOR_WARNING = "#F59E0B"      # ambre
COLOR_DANGER = "#EF4444"       # rouge

CUSTOM_CSS = """
<style>
    /* Header gradient */
    .pm-header {
        background: linear-gradient(135deg, #0EA5E9 0%, #10B981 100%);
        padding: 1.5rem 2rem;
        border-radius: 0.5rem;
        margin-bottom: 1.5rem;
        color: white;
    }
    .pm-header h1 {
        margin: 0;
        font-size: 1.8rem;
    }
    .pm-header p {
        margin: 0.25rem 0 0 0;
        opacity: 0.95;
        font-size: 0.95rem;
    }

    /* KPI cards */
    .pm-kpi {
        background: #F9FAFB;
        border-left: 4px solid #0EA5E9;
        padding: 1rem 1.25rem;
        border-radius: 0.25rem;
    }
    .pm-kpi-label {
        font-size: 0.85rem;
        color: #6B7280;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin: 0;
    }
    .pm-kpi-value {
        font-size: 1.75rem;
        font-weight: 700;
        color: #111827;
        margin: 0.25rem 0 0 0;
    }
    .pm-kpi-detail {
        font-size: 0.8rem;
        color: #9CA3AF;
        margin: 0.25rem 0 0 0;
    }

    /* Pastille colorée */
    .pm-badge {
        display: inline-block;
        padding: 0.15rem 0.65rem;
        border-radius: 9999px;
        font-size: 0.85rem;
        font-weight: 500;
        color: white;
    }

    /* Réduit l'espacement par défaut Streamlit */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    /* Sidebar plus discrète */
    [data-testid="stSidebar"] {
        background: #F9FAFB;
    }
</style>
"""


def page_setup(
    title: str,
    icon: str = "🚇",
    layout: Literal["centered", "wide"] = "wide",
) -> None:
    """Initialise la config de la page et applique le CSS custom.

    À appeler en première instruction de chaque page.
    """
    st.set_page_config(
        page_title=f"{title} · ParisMove AI",
        page_icon=icon,
        layout=layout,
        initial_sidebar_state="expanded",
    )
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def header(title: str, subtitle: str = "") -> None:
    """Affiche le header gradient ParisMove AI."""
    st.markdown(
        f"""
        <div class="pm-header">
            <h1>{title}</h1>
            {f'<p>{subtitle}</p>' if subtitle else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )


def kpi_card(label: str, value: str, detail: str = "") -> None:
    """Affiche une carte KPI stylée."""
    st.markdown(
        f"""
        <div class="pm-kpi">
            <p class="pm-kpi-label">{label}</p>
            <p class="pm-kpi-value">{value}</p>
            {f'<p class="pm-kpi-detail">{detail}</p>' if detail else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )


def badge(text: str, color: str = COLOR_PRIMARY) -> str:
    """Retourne le HTML d'un badge coloré (à intégrer dans st.markdown)."""
    return f'<span class="pm-badge" style="background:{color}">{text}</span>'


def sidebar_footer() -> None:
    """Affiche un footer dans la sidebar : credits + état des sources."""
    with st.sidebar:
        st.divider()
        st.markdown(
            """
            <div style='font-size:0.8rem;color:#6B7280;'>
                <strong>ParisMove AI</strong><br>
                Sources :<br>
                · PRIM IDFM (transports)<br>
                · AQICN / Airparif (qualité air)<br>
                · Open-Meteo (météo)<br>
                <br>
                Projet étudiant — Sup de Vinci
            </div>
            """,
            unsafe_allow_html=True,
        )
