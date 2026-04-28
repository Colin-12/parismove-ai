"""Tools data-aware pour le coach.

Chaque tool retourne un BLOC DE TEXTE FACTUEL formaté que le LLM intègre
dans sa réponse. Le LLM ne voit JAMAIS la BDD directement, donc il ne peut
pas inventer de chiffres (anti-hallucination niveau 1).

Chaque chiffre fourni est accompagné de sa source et de son horodatage,
que le LLM doit citer (anti-hallucination niveau 2).

Si une donnée n'est pas disponible, le tool retourne un message explicite
"Pas de données disponibles" — au LLM ensuite de le dire à l'utilisateur.
"""
from __future__ import annotations

from datetime import datetime

from healthscore.compare import compare_journeys, score_journey
from healthscore.scoring import grade_color
from shared.db import LineLookup
from sqlalchemy import Engine, text


def _format_age(when: datetime | None) -> str:
    """Retourne 'il y a Xmin' ou 'il y a Xh'."""
    if when is None:
        return "?"
    now = datetime.now(when.tzinfo) if when.tzinfo else datetime.now()
    delta = now - when
    minutes = int(delta.total_seconds() / 60)
    if minutes < 60:
        return f"il y a {minutes} min"
    hours = minutes // 60
    return f"il y a {hours}h"


def get_current_air_quality(engine: Engine, zone: str | None = None) -> str:
    """Retourne un état actualisé de la qualité de l'air.

    Args:
        engine: connexion BDD
        zone: filtre optionnel sur le nom de station (matching partiel)

    Returns:
        Texte multi-lignes avec les mesures par station, ou message d'absence.
    """
    sql = text(
        """
        SELECT DISTINCT ON (station_id)
            station_id, station_name, aqi, pm25, pm10, no2, measured_at, attribution
        FROM air_measurements
        WHERE measured_at >= NOW() - INTERVAL '6 hours'
        ORDER BY station_id, measured_at DESC
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql).fetchall()

    if not rows:
        return "[NO_DATA] Aucune mesure de qualité de l'air disponible (< 6h)."

    if zone is not None:
        zone_lower = zone.lower()
        rows = [r for r in rows if zone_lower in (r.station_name or "").lower()]
        if not rows:
            return f"[NO_DATA] Aucune mesure récente pour la zone '{zone}'."

    lines = ["[DATA] Qualité de l'air actuelle :"]
    for r in rows:
        age = _format_age(r.measured_at)
        parts = [f"AQI={r.aqi or '?'}"]
        if r.pm25 is not None:
            parts.append(f"PM2.5={r.pm25:.0f} µg/m³")
        if r.pm10 is not None:
            parts.append(f"PM10={r.pm10:.0f} µg/m³")
        if r.no2 is not None:
            parts.append(f"NO2={r.no2:.0f} µg/m³")
        attribution = r.attribution or "AQICN"
        lines.append(
            f"  - {r.station_name} : {', '.join(parts)} "
            f"(source: {attribution}, mesuré {age})"
        )

    # Aide pour l'interprétation
    lines.append("")
    lines.append(
        "[GUIDE] Seuils OMS PM2.5 : ≤5 = excellent, 5-15 = acceptable, "
        "15-25 = modéré, 25-50 = mauvais, >50 = dangereux."
    )
    return "\n".join(lines)


def get_current_weather(engine: Engine, point: str | None = None) -> str:
    """Retourne la météo actuelle aux différents points d'observation."""
    sql = text(
        """
        SELECT DISTINCT ON (point_id)
            point_id, point_name, temperature_c, precipitation_mm,
            wind_speed_ms, humidity_pct, weather_code, observed_at
        FROM weather_observations
        WHERE observed_at >= NOW() - INTERVAL '3 hours'
        ORDER BY point_id, observed_at DESC
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql).fetchall()

    if not rows:
        return "[NO_DATA] Aucune observation météo disponible (< 3h)."

    if point is not None:
        point_lower = point.lower()
        rows = [
            r for r in rows
            if point_lower in (r.point_name or "").lower()
            or point_lower in (r.point_id or "").lower()
        ]
        if not rows:
            return f"[NO_DATA] Aucune observation pour '{point}'."

    lines = ["[DATA] Météo actuelle :"]
    for r in rows:
        age = _format_age(r.observed_at)
        parts = []
        if r.temperature_c is not None:
            parts.append(f"{r.temperature_c:.1f}°C")
        if r.humidity_pct is not None:
            parts.append(f"humidité {r.humidity_pct:.0f}%")
        if r.precipitation_mm is not None:
            if r.precipitation_mm > 0:
                parts.append(f"pluie {r.precipitation_mm:.1f}mm")
            else:
                parts.append("pas de pluie")
        if r.wind_speed_ms is not None:
            parts.append(f"vent {r.wind_speed_ms:.1f} m/s")

        lines.append(
            f"  - {r.point_name} : {', '.join(parts)} "
            f"(source: Open-Meteo, observé {age})"
        )
    return "\n".join(lines)


def get_current_traffic(
    engine: Engine, line_query: str | None = None
) -> str:
    """Retourne un résumé du trafic récent.

    Args:
        line_query: filtre optionnel sur nom court de ligne (T2, RER A, 258...)
    """
    line_lookup = LineLookup.from_database(engine)

    if line_query is not None:
        # Filtre par ligne : retard moyen sur cette ligne
        # On résout d'abord le line_id à partir du nom court fourni
        matching = [
            (lid, info)
            for lid, info in line_lookup.by_line_id.items()
            if info.short_name and info.short_name.lower() == line_query.lower()
        ]
        if not matching:
            return (
                f"[NO_DATA] Aucune ligne nommée '{line_query}' trouvée dans le "
                "référentiel IDFM. Essayez avec le nom court exact (ex: 'T2', "
                "'RER A', '258')."
            )

        lids = [lid for lid, _ in matching]
        info = matching[0][1]

        sql = text(
            """
            SELECT
                COUNT(*) AS samples,
                AVG(delay_seconds)::FLOAT AS avg_delay,
                MAX(recorded_at) AS latest
            FROM stop_visits
            WHERE line_id = ANY(:lids)
              AND recorded_at >= NOW() - INTERVAL '2 hours'
              AND delay_seconds IS NOT NULL
            """
        )
        with engine.connect() as conn:
            row = conn.execute(sql, {"lids": lids}).one()

        if row.samples == 0:
            return (
                f"[NO_DATA] Aucune mesure récente pour la ligne {info.short_name} "
                "sur les 2 dernières heures."
            )

        avg_delay_min = (row.avg_delay or 0) / 60
        return (
            f"[DATA] Ligne {info.short_name} ({info.transport_mode or '?'}, "
            f"{info.network_name or '?'}) : "
            f"{row.samples} passages observés sur les 2 dernières heures, "
            f"retard moyen {avg_delay_min:.1f} min "
            f"(source: PRIM IDFM, dernier {_format_age(row.latest)})."
        )

    # Pas de filtre : vue d'ensemble du trafic récent
    sql = text(
        """
        SELECT
            COUNT(*) AS total_samples,
            AVG(delay_seconds)::FLOAT AS overall_avg_delay,
            COUNT(DISTINCT line_id) AS distinct_lines,
            MAX(recorded_at) AS latest
        FROM stop_visits
        WHERE recorded_at >= NOW() - INTERVAL '2 hours'
          AND delay_seconds IS NOT NULL
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql).one()

    if not row.total_samples:
        return "[NO_DATA] Aucun passage capté sur les 2 dernières heures."

    avg_delay_sec = row.overall_avg_delay or 0
    return (
        f"[DATA] Vue d'ensemble du trafic IDF (2 dernières heures) : "
        f"{row.total_samples} passages observés sur {row.distinct_lines} lignes "
        f"distinctes, retard moyen {avg_delay_sec:.0f} secondes "
        f"(source: PRIM IDFM, dernier {_format_age(row.latest)})."
    )


def score_user_journey(
    engine: Engine,
    journey_id: str,
    journey_label: str,
    waypoints: list[tuple[float, float]],
) -> str:
    """Calcule le score santé d'un trajet et retourne un résumé textuel."""
    if not waypoints:
        return "[NO_DATA] Aucun waypoint fourni pour le trajet."

    score = score_journey(engine, journey_id, journey_label, waypoints)

    lines = [f"[DATA] Score santé du trajet '{score.journey_label}' :"]
    lines.append(
        f"  Grade {score.grade.value} ({score.overall_score:.0f}/100, "
        f"couleur {grade_color(score.grade)})"
    )
    lines.append(f"  Pollution : {score.pollution_score:.0f}/100")
    lines.append(f"  Météo     : {score.weather_score:.0f}/100")
    lines.append(f"  Trafic    : {score.traffic_score:.0f}/100")
    if score.warnings:
        lines.append("  Limites :")
        for w in score.warnings:
            lines.append(f"    ⚠️ {w}")
    return "\n".join(lines)


def compare_user_journeys(
    engine: Engine,
    journeys: list[tuple[str, str, list[tuple[float, float]]]],
) -> str:
    """Compare plusieurs trajets et retourne un résumé textuel."""
    if len(journeys) < 2:
        return "[NO_DATA] Il faut au moins 2 trajets à comparer."

    comparison = compare_journeys(engine, journeys)

    lines = ["[DATA] Comparaison de trajets :"]
    sorted_j = sorted(comparison.journeys, key=lambda j: j.overall_score, reverse=True)
    for i, j in enumerate(sorted_j, start=1):
        marker = " (recommandé)" if j.journey_id == comparison.best_journey_id else ""
        lines.append(
            f"  {i}. {j.journey_label} : {j.grade.value} "
            f"({j.overall_score:.0f}/100){marker}"
        )

    if comparison.is_significant:
        lines.append(
            f"  → Différence significative ({comparison.score_gap:.0f} pts d'écart)."
        )
    else:
        lines.append(
            f"  → Différence minime ({comparison.score_gap:.0f} pts), "
            "trajets équivalents."
        )
    return "\n".join(lines)


def list_capabilities() -> str:
    """Retourne la liste des choses que le coach sait faire."""
    return """[DATA] Capacités du coach ParisMove AI :

Le coach peut répondre aux types de questions suivants en utilisant des
données réelles temps-réel :

  1. Qualité de l'air (sources : Airparif via AQICN, modèles CAMS via Open-Meteo)
     "Comment est l'air à Paris ?"
     "What's the air quality at La Défense?"

  2. Météo (source : Open-Meteo, modèles ECMWF)
     "Quel temps il fait à Versailles ?"
     "Is it raining in Paris?"

  3. Trafic (source : PRIM IDFM)
     "Comment se passe le trafic en ce moment ?"
     "Quel est le retard moyen sur le RER A ?"

  4. Score santé d'un trajet (combine pollution + météo + trafic)
     Score de A (excellent) à E (à éviter), basé sur les seuils OMS.

  5. Comparaison de trajets
     "Compare le RER A et le métro 1 pour aller à La Défense"

Pour les questions hors de ces sujets, le coach répondra en se basant sur
sa connaissance générale, en signalant clairement qu'il n'utilise pas de
données temps-réel.
"""
