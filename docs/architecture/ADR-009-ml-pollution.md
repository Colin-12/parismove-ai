# ADR-009 — Modèle ML pollution (XGBoost PM2.5)

## Statut
Accepté — mai 2026 (mis à jour mai 2026)

## Contexte
Pour démontrer une compétence ML au-delà du data engineering et de l'IA
générative, le projet devait inclure un modèle de prédiction. Les données
AQICN et Open-Meteo déjà ingérées se prêtent à la prédiction de PM2.5 à H+1.

## Décision
Service `services/ml-pollution` : modèle **XGBoost global** avec
`station_id` comme feature catégorielle (`enable_categorical=True`),
entraîné sur 400 jours de données (historique Airparif 2025-2026 + ingestion
temps-réel).

**Features** :

| Catégorie | Features |
|-----------|----------|
| Temporelles | `heure`, `jour_semaine`, `mois` |
| Lag PM2.5 | `pm25_h1`, `pm25_h2`, `pm25_h3`, `pm25_h24` |
| Météo | `temperature_c`, `humidity_pct`, `wind_speed_ms`, `precipitation_mm` |
| Géographique | `station_id` (catégoriel) |

**Target** : `log(pm25+1)` — la distribution PM2.5 est très asymétrique
(nombreux pics extrêmes rares). La transformation logarithmique stabilise
la distribution et améliore significativement les prédictions XGBoost.
Les métriques sont calculées après reconversion via `expm1()`.

**Exclusion** : la station `@5722` (Paris, trafic routier) est exclue de
l'entraînement — variation horaire moyenne de 9 µg/m³ vs 1-3 µg/m³ pour
les autres stations, ce qui bruite le modèle global.

**Validation** : split chronologique 80/20 (pas aléatoire — évite la
fuite temporelle sur séries temporelles).

**Persistance** : `pm25_xgb.joblib` + `pm25_xgb.meta.json` (métriques,
hyperparamètres, flag `log_transform` lu par `predict.py` pour la
reconversion automatique).

**Données historiques** : 1 an de mesures PM2.5 importé depuis le portail
Open Data Airparif (`data-airparif-asso.opendata.arcgis.com`). Météo
historique via Open-Meteo Historical API (ERA5, gratuit, depuis 1940).

## Conséquences
- ✅ Compétence ML démontrée : feature engineering, validation chronologique,
  persistance, inférence — tout le cycle est couvert
- ✅ Métriques finales : MAE **2.63 µg/m³**, RMSE **5.38 µg/m³** (8 stations,
  49 430 échantillons d'entraînement)
- ✅ Amélioration de -77% vs baseline initial (MAE 11.34 µg/m³ sur 28 jours)
- ⚠️ Réentraînement manuel via `python -m ml_pollution.cli train --days 400`
- ⚠️ Pas de versioning de modèle (un seul `.joblib` à la fois)
- ⚠️ Données Airparif publiées avec 5-6h de délai — la prédiction H+1
  porte sur H+1 depuis la dernière mesure disponible, pas depuis maintenant