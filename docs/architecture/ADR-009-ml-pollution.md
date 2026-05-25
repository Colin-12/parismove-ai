# ADR-009 — Modèle ML pollution (XGBoost PM2.5)

## Statut
Accepté — mai 2026

## Contexte
Pour démontrer une compétence ML au-delà du data engineering et de l'IA
générative, le projet devait inclure un modèle de prédiction. Les données
AQICN et Open-Meteo déjà ingérées se prêtent à la prédiction de PM2.5 à H+1.

## Décision
Service `services/ml-pollution` : modèle **XGBoost global** avec
`station_id` comme feature catégorielle (`enable_categorical=True`),
entraîné sur les données des 28 derniers jours.

**Features** : heure, jour_semaine, mois, pm25_h1, pm25_h24,
temperature_c, humidity_pct, wind_speed_ms, precipitation_mm, station_id.

**Validation** : split chronologique 80/20 (pas aléatoire — évite la
fuite temporelle sur séries temporelles).

**Persistance** : `pm25_xgb.joblib` + `pm25_xgb.meta.json` (métriques
et hyperparamètres lisibles par le dashboard sans charger le modèle).

Un modèle global plutôt que 8 modèles par station : à 28 jours de données,
diviser par station donnerait des modèles sur-fittés. XGBoost apprend
les spécificités locales via l'encodage catégoriel de `station_id`.

## Conséquences
- ✅ Compétence ML démontrée : feature engineering, validation chronologique,
  persistance, inférence — tout le cycle est couvert
- ✅ Métriques actuelles : MAE 8.13 µg/m³, RMSE 11.79 µg/m³ (7 stations)
- ⚠️ Réentraînement manuel via `ml-pollution train` — pas de cron automatique
- ⚠️ Pas de versioning de modèle (un seul `.joblib` à la fois)
