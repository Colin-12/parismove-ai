"""Transforme les réponses SIRI-Lite de PRIM en objets `StopVisit`.

Le format SIRI est verbeux et imbriqué. Ce module isole toute la complexité
de parsing — le reste du pipeline ne manipule que des `StopVisit`.

Robustesse face aux variations réelles de PRIM :

* `PublishedLineName` peut être absent, on se rabat sur `JourneyNote` ou
  on extrait un identifiant court depuis `LineRef`.
* `VehicleMode` est rarement peuplé en dehors des exemples de doc. On
  déduit le mode depuis le préfixe de ligne ou le transporteur.
* Pour les bus (notamment via Transdev), seul `AimedDepartureTime` /
  `ExpectedDepartureTime` est renseigné — on capture donc les deux paires.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from shared.schemas import StopVisit, TransportMode


# Préfixes d'identifiants de ligne connus, pour déduire le mode de transport
# quand l'API ne renvoie pas explicitement VehicleMode.
# Exemples de LineRef : STIF:Line::C01371: (métro 1), STIF:Line::C01742: (RER B)
_KNOWN_LINE_PREFIXES: dict[str, TransportMode] = {
    # RER Transilien (lignes SNCF + RATP)
    "C01742": TransportMode.RER,  # RER B
    "C01743": TransportMode.RER,  # RER A sud (co-exploité)
    "C01727": TransportMode.RER,  # RER C
    "C01728": TransportMode.RER,  # RER D
    "C01729": TransportMode.RER,  # RER E
}


def _extract_value(field: Any) -> str | None:
    """Extrait la valeur d'un champ SIRI.

    PRIM retourne soit un dict `{"value": "..."}`, soit une liste de ces dicts,
    soit une chaîne simple. On normalise tout ça.
    """
    if field is None:
        return None
    if isinstance(field, str):
        return field.strip() or None
    if isinstance(field, dict) and "value" in field:
        return _extract_value(field["value"])
    if isinstance(field, list) and field:
        # Retourne la première valeur non vide
        for item in field:
            extracted = _extract_value(item)
            if extracted:
                return extracted
        return None
    return None


def _parse_datetime(raw: str | None) -> datetime | None:
    """Parse un horodatage ISO 8601 tel que retourné par PRIM."""
    if not raw:
        return None
    normalized = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _short_line_code(line_id: str | None) -> str | None:
    """Extrait un code court depuis un LineRef.

    `STIF:Line::C01371:` -> `C01371`. Sert de fallback quand
    `PublishedLineName` est absent.
    """
    if not line_id:
        return None
    parts = line_id.split(":")
    for part in reversed(parts):
        if part:
            return part
    return None


def _parse_transport_mode(
    raw_mode: Any, line_id: str | None, operator: str | None
) -> TransportMode:
    """Déduit le mode de transport en combinant plusieurs sources.

    Ordre de priorité :
      1. Champ explicite VehicleMode
      2. Préfixe connu de l'identifiant de ligne
      3. Opérateur (SNCF -> train/rer, RATP -> inconnu car trop varié)
    """
    # 1. Champ explicite
    value = _extract_value(raw_mode)
    if value:
        mapping = {
            "metro": TransportMode.METRO,
            "rail": TransportMode.RER,
            "tram": TransportMode.TRAM,
            "bus": TransportMode.BUS,
        }
        mapped = mapping.get(value.lower())
        if mapped is not None:
            return mapped

    # 2. Préfixe connu
    line_code = _short_line_code(line_id)
    if line_code and line_code in _KNOWN_LINE_PREFIXES:
        return _KNOWN_LINE_PREFIXES[line_code]

    # 3. Opérateur pour les cas les plus évidents
    if operator and "SNCF" in operator.upper():
        return TransportMode.TRAIN

    return TransportMode.UNKNOWN


def _extract_line_name(
    journey: dict[str, Any], line_id: str | None
) -> str | None:
    """Extrait un nom d'affichage pour la ligne.

    Essaie dans l'ordre : PublishedLineName, JourneyNote, code court de LineRef.
    """
    for field_name in ("PublishedLineName", "JourneyNote"):
        value = _extract_value(journey.get(field_name))
        if value:
            return value
    return _short_line_code(line_id)


def _extract_operator(journey: dict[str, Any]) -> str | None:
    """Extrait un nom d'opérateur lisible.

    `STIF:Operator::RATP:` -> `RATP`.
    """
    raw = _extract_value(journey.get("OperatorRef"))
    if not raw:
        return None
    parts = [p for p in raw.split(":") if p and p != "STIF" and p != "Operator"]
    return parts[-1] if parts else raw


def _parse_monitored_visit(
    visit: dict[str, Any], response_timestamp: datetime
) -> StopVisit | None:
    """Parse un MonitoredStopVisit unique. Retourne None si invalide."""
    journey = visit.get("MonitoredVehicleJourney", {})
    monitored_call = journey.get("MonitoredCall", {})

    stop_id = _extract_value(visit.get("MonitoringRef"))
    line_id = _extract_value(journey.get("LineRef"))

    if not stop_id or not line_id:
        return None

    operator = _extract_operator(journey)

    return StopVisit(
        stop_id=stop_id,
        line_id=line_id,
        vehicle_journey_id=_extract_value(journey.get("FramedVehicleJourneyRef")),
        line_name=_extract_line_name(journey, line_id),
        operator=operator,
        direction=_extract_value(journey.get("DirectionName"))
        or _extract_value(journey.get("DestinationName"))
        or _extract_value(monitored_call.get("DestinationDisplay")),
        transport_mode=_parse_transport_mode(
            journey.get("VehicleMode"), line_id, operator
        ),
        aimed_arrival=_parse_datetime(
            _extract_value(monitored_call.get("AimedArrivalTime"))
        ),
        expected_arrival=_parse_datetime(
            _extract_value(monitored_call.get("ExpectedArrivalTime"))
        ),
        aimed_departure=_parse_datetime(
            _extract_value(monitored_call.get("AimedDepartureTime"))
        ),
        expected_departure=_parse_datetime(
            _extract_value(monitored_call.get("ExpectedDepartureTime"))
        ),
        arrival_status=_extract_value(monitored_call.get("ArrivalStatus")),
        departure_status=_extract_value(monitored_call.get("DepartureStatus")),
        recorded_at=_parse_datetime(_extract_value(visit.get("RecordedAtTime")))
        or response_timestamp,
        source="prim",
    )


def parse_stop_monitoring_response(raw: dict[str, Any]) -> list[StopVisit]:
    """Transforme une réponse SIRI-Lite "stop-monitoring" en `StopVisit`s.

    Args:
        raw: le JSON brut de l'API PRIM.

    Returns:
        Liste de passages normalisés, triée par meilleur horaire disponible.
        Les visites sans aucun horaire sont placées en fin de liste.
    """
    service_delivery = raw.get("Siri", {}).get("ServiceDelivery", {})
    response_timestamp = _parse_datetime(
        service_delivery.get("ResponseTimestamp")
    ) or datetime.now().astimezone()

    deliveries = service_delivery.get("StopMonitoringDelivery", [])
    visits: list[StopVisit] = []

    for delivery in deliveries:
        for raw_visit in delivery.get("MonitoredStopVisit", []):
            parsed = _parse_monitored_visit(raw_visit, response_timestamp)
            if parsed is not None:
                visits.append(parsed)

    # Tri par meilleur horaire disponible, les visites sans horaire en fin
    visits.sort(key=lambda v: (v.best_time is None, v.best_time))
    return visits
