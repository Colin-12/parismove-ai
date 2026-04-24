"""Transforme les réponses SIRI-Lite de PRIM en objets `StopVisit`.

Le format SIRI est verbeux et imbriqué. Ce module isole toute la complexité
de parsing — le reste du pipeline ne manipule que des `StopVisit`.

Structure de la réponse SIRI "stop-monitoring" (résumée) :

    {
      "Siri": {
        "ServiceDelivery": {
          "ResponseTimestamp": "2026-04-24T10:00:00Z",
          "StopMonitoringDelivery": [
            {
              "MonitoredStopVisit": [
                {
                  "RecordedAtTime": "...",
                  "MonitoringRef": {"value": "STIF:StopPoint:Q:..."},
                  "MonitoredVehicleJourney": {
                    "LineRef": {"value": "STIF:Line::C01371:"},
                    "DirectionName": [{"value": "La Défense"}],
                    "MonitoredCall": {
                      "AimedArrivalTime": "...",
                      "ExpectedArrivalTime": "...",
                      "ArrivalStatus": "onTime"
                    },
                    "PublishedLineName": [{"value": "1"}],
                    "VehicleMode": ["metro"]
                  }
                }
              ]
            }
          ]
        }
      }
    }
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from shared.schemas import StopVisit, TransportMode


def _extract_value(field: Any) -> str | None:
    """Extrait la valeur d'un champ SIRI.

    PRIM retourne soit un dict `{"value": "..."}`, soit une liste de ces dicts,
    soit une chaîne simple. On normalise tout ça.
    """
    if field is None:
        return None
    if isinstance(field, str):
        return field
    if isinstance(field, dict) and "value" in field:
        return str(field["value"])
    if isinstance(field, list) and field:
        return _extract_value(field[0])
    return None


def _parse_datetime(raw: str | None) -> datetime | None:
    """Parse un horodatage ISO 8601 tel que retourné par PRIM."""
    if not raw:
        return None
    # PRIM peut retourner avec ou sans timezone, avec 'Z' ou '+00:00'
    normalized = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _parse_transport_mode(raw: Any) -> TransportMode:
    """Traduit le VehicleMode SIRI en TransportMode."""
    value = _extract_value(raw)
    if value is None:
        return TransportMode.UNKNOWN

    mapping = {
        "metro": TransportMode.METRO,
        "rail": TransportMode.RER,  # PRIM utilise 'rail' pour RER et trains
        "tram": TransportMode.TRAM,
        "bus": TransportMode.BUS,
    }
    return mapping.get(value.lower(), TransportMode.UNKNOWN)


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

    return StopVisit(
        stop_id=stop_id,
        line_id=line_id,
        vehicle_journey_id=_extract_value(journey.get("FramedVehicleJourneyRef")),
        line_name=_extract_value(journey.get("PublishedLineName")),
        direction=_extract_value(journey.get("DirectionName")),
        transport_mode=_parse_transport_mode(journey.get("VehicleMode")),
        aimed_arrival=_parse_datetime(
            _extract_value(monitored_call.get("AimedArrivalTime"))
        ),
        expected_arrival=_parse_datetime(
            _extract_value(monitored_call.get("ExpectedArrivalTime"))
        ),
        arrival_status=_extract_value(monitored_call.get("ArrivalStatus")),
        recorded_at=_parse_datetime(_extract_value(visit.get("RecordedAtTime")))
        or response_timestamp,
        source="prim",
    )


def parse_stop_monitoring_response(raw: dict[str, Any]) -> list[StopVisit]:
    """Transforme une réponse SIRI-Lite "stop-monitoring" en `StopVisit`s.

    Args:
        raw: le JSON brut de l'API PRIM.

    Returns:
        Liste de passages normalisés, triée par horaire prévu croissant.
        Les visites invalides ou incomplètes sont silencieusement ignorées.
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

    # Tri par horaire prévu (ceux sans horaire à la fin)
    visits.sort(
        key=lambda v: (v.expected_arrival is None, v.expected_arrival)
    )
    return visits
