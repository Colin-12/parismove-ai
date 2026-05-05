# ml-pollution

Service ML pour ParisMove AI : entraîne un modèle XGBoost qui prédit
la concentration PM2.5 à H+1 sur les stations Airparif d'Île-de-France.

## Installation

```bash
# Depuis la racine du monorepo
pip install -e services/ml-pollution
```

## Utilisation

### Entraîner le modèle

```bash
ml-pollution train --days 30
```

Le modèle est sauvegardé dans `services/ml-pollution/models/pm25_xgb.joblib`,
avec ses métadonnées dans `pm25_xgb.meta.json`.

Options :
- `--days N` : fenêtre temporelle d'entraînement (défaut 30)
- `--test-ratio 0.2` : proportion gardée pour le test (split chronologique)
- `--n-estimators 200`, `--max-depth 5`, `--learning-rate 0.1` :
  hyperparamètres XGBoost

### Évaluer le modèle persisté

```bash
ml-pollution evaluate
```

Affiche les métadonnées et métriques du dernier entraînement.

### Prédire pour une station

```bash
ml-pollution predict @5722
```

Prédit le PM2.5 pour l'heure suivante à partir des dernières mesures.

## Architecture

Le modèle est **global** (un seul `.joblib` pour toutes les stations) avec
`station_id` comme feature catégorielle. Cela permet :
- D'utiliser tout le volume de mesures (250+ vs 30/station)
- D'apprendre les spécificités locales via l'encoding catégoriel
- D'éviter le sur-apprentissage qui guette des modèles entraînés sur
  trop peu d'observations

Voir `docs/architecture/ADR-009-ml-pollution.md` pour plus de détails.

## Features

| Catégorie | Features | Source |
|-----------|----------|--------|
| Temporelles | `heure`, `jour_semaine`, `mois` | Timestamp |
| Lag PM2.5 | `pm25_h1` (il y a 1h), `pm25_h24` (il y a 24h) | `air_measurements` |
| Météo | `temperature_c`, `humidity_pct`, `wind_speed_ms`, `precipitation_mm` | `weather_observations` |
| Géo | `station_id` (catégoriel) | `air_measurements` |

## Limitations connues

- Avec 6 jours de data, MAE attendue ~5-10 µg/m³ (acceptable mais pas wow)
- Pas de ré-entraînement automatique (à lancer manuellement)
- Horizon de prédiction limité à H+1
- Modèle non versionné (un seul `.joblib` à la fois)

## Tests

```bash
pytest services/ml-pollution
```

Couvre features, persistence et split chronologique. Pas de test
end-to-end avec BDD réelle (nécessiterait une fixture Postgres lourde).

## Inspiration

Concept issu de
[OptiMobility-BDIA-2025](https://github.com/Colin-12/OptiMobility-BDIA-2025),
amélioré ici avec :
- Météo en features supplémentaires
- Modèle multi-stations vs mono-station
- Architecture monorepo + tests + ADR
