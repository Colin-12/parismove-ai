# ADR-004 — Calcul du score santé de trajet

## Statut
Accepté — avril 2026

## Contexte
ParisMove AI doit fournir une fonctionnalité différenciante : aider
l'utilisateur à choisir le trajet le moins polluant, pas seulement le
plus rapide. Il faut définir comment combiner pollution, météo et trafic
en un indicateur lisible.

## Décision
Score multicritère **A-E façon Nutri-Score** combinant :

| Dimension | Poids | Source |
|-----------|-------|--------|
| Pollution | 60 %  | AQICN / Airparif (stations à < 5 km) |
| Météo     | 30 %  | Open-Meteo (point le plus proche) |
| Trafic    | 10 %  | PRIM IDFM (lignes traversées) |

Le trajet est décrit par une liste de coordonnées GPS (pas d'identifiants
d'arrêts) pour rester générique à tous les modes. Le calcul géospatial
se fait en Python pur (haversine) — PostGIS non nécessaire à notre échelle.

## Conséquences
- ✅ UX intuitive : format A-E éprouvé (Nutri-Score, Yuka)
- ✅ Pondération configurable en paramètre sans changer le code
- ✅ Module testable indépendamment (un fichier par sub-score)
- ⚠️ Précision spatiale limitée par le nombre de capteurs (7 stations)
  — warning affiché si la station la plus proche est à > 5 km
- ⚠️ Tracé en vol d'oiseau entre les waypoints (pas de routage multimodal)
