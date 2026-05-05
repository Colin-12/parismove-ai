# ADR 009 — Service ML pollution (XGBoost PM2.5)

**Statut :** Accepté
**Date :** 2026-05
**Auteur :** Colin

## Contexte

Le projet ParisMove AI dispose désormais d'un dashboard à 4 pages + Coach
IA. Pour rester sur la trajectoire pédagogique du Mastère 2 Big Data & IA,
il est nécessaire de démontrer une **compétence ML**, pas seulement de
data engineering et d'IA générative.

Un précédent projet personnel ([OptiMobility-BDIA-2025]
(https://github.com/Colin-12/OptiMobility-BDIA-2025)) avait expérimenté un
modèle XGBoost pour prédire la concentration PM2.5 à H+1 sur une station
Paris unique. Cette PR transpose et améliore ce concept dans
l'architecture monorepo de ParisMove AI.

## Décision

Créer un nouveau service `services/ml-pollution/` (6e service du
monorepo) qui :

1. **Lit** les tables `air_measurements` et `weather_observations` de
   Supabase
2. **Construit** des features (temporelles + lag + météo + station_id)
3. **Entraîne** un modèle XGBoost global avec station_id comme feature
   catégorielle
4. **Persiste** le modèle entraîné dans
   `services/ml-pollution/models/pm25_xgb.joblib`
5. **Prédit** la concentration PM2.5 à H+1 pour une station donnée
6. **Expose** une CLI (`ml-pollution train|evaluate|predict`)

Une nouvelle page dashboard `5_Prevision_air.py` consomme le modèle
pour afficher les prédictions et le backtest visuel.

## Points clés

### 1. Modèle global vs un modèle par station

**Décision : modèle global** avec `station_id` comme feature catégorielle.

**Justification** :
- À 6 jours de data, on a ~30 mesures par station × 8 stations = 240
  observations totales. Diviser en 8 modèles donnerait des modèles
  sur-fittés sur 30 points chacun.
- XGBoost gère nativement les variables catégorielles via
  `enable_categorical=True` (algo `hist`).
- Le modèle apprend implicitement les spécificités locales (Paris Halles
  est plus pollué que Cergy en moyenne) sans qu'on doive le hard-coder.
- Quand on aura plus de données (dans 2-3 mois), on pourra envisager
  des modèles dédiés sans changer l'API.

### 2. Features du modèle

Inspirées d'OptiMobility (5 features de base) + enrichissement météo :

| Catégorie | Features | Source |
|-----------|----------|--------|
| Temporelles | `heure`, `jour_semaine`, `mois` | Timestamp |
| Lag PM2.5 | `pm25_h1`, `pm25_h24` | `air_measurements` |
| Météo | `temperature_c`, `humidity_pct`, `wind_speed_ms`, `precipitation_mm` | `weather_observations` (point le plus proche) |
| Géographique | `station_id` (catégoriel) | `air_measurements` |

Le mapping station Airparif → point météo le plus proche est calculé
par distance haversine au moment de la jointure (via `merge_asof`).

### 3. Split chronologique pour la validation

**Décision : split chronologique 80/20**, pas aléatoire.

**Justification** :
Sur des séries temporelles, un split aléatoire crée de la **fuite
temporelle** (le modèle apprend du futur pour prédire le passé).
Le split chronologique simule la prod : on entraîne sur l'historique
et on évalue sur les données les plus récentes.

### 4. Persistance via joblib + métadonnées JSON

**Décision** : 2 fichiers — le modèle binaire (joblib) et un JSON de
métadonnées (date d'entraînement, métriques, hyperparamètres,
fenêtre de data).

Le JSON est lu par le dashboard pour afficher les KPIs du modèle
(MAE, RMSE, n_train) sans charger le modèle complet.

### 5. Pas de réentraînement automatique (initial)

**Décision** : entraînement **manuel** via `ml-pollution train`.

**Justification** :
- Plus simple à démarrer et à debugger
- Avec 6 jours de data, ré-entraîner tous les jours n'apporte rien
- Quand le modèle sera mature, on pourra ajouter un cron GitHub Actions
  hebdomadaire (ADR ultérieur si besoin)

## Architecture

```
services/ml-pollution/
├── pyproject.toml
├── README.md
├── models/                     # créé au premier `train` (gitignored)
│   ├── pm25_xgb.joblib
│   └── pm25_xgb.meta.json
├── src/ml_pollution/
│   ├── __init__.py
│   ├── py.typed
│   ├── config.py               # settings + chemin du dossier modèles
│   ├── data_access.py          # fetch + jointure météo (merge_asof)
│   ├── features.py             # construction des features
│   ├── persistence.py          # save/load joblib + JSON
│   ├── train.py                # entraînement + métriques
│   ├── predict.py              # inférence H+1 + backtest
│   └── cli.py                  # commandes train, evaluate, predict
└── tests/
    ├── test_features.py
    ├── test_persistence.py
    └── test_train.py
```

## Conséquences

### Positives

- **Compétence ML démontrée** : feature engineering, validation,
  persistence, inférence — tout y est.
- **Réutilisation pédagogique** : on a capitalisé sur OptiMobility tout
  en l'améliorant (ajout météo, modèle global multi-stations).
- **Dashboard plus impressionnant** : 5 pages + chat IA, dont une page
  avec un vrai modèle ML qui tourne.
- **Architecture cohérente** : 6e service du monorepo, suit les mêmes
  conventions que les 5 autres (pyproject, py.typed, tests, ADR).

### Négatives

- **Performance limitée** par le volume de data. Avec 6 jours, MAE
  attendue ~5-10 µg/m³ sur PM2.5. Acceptable pour une démo, pas pour
  de la prod réelle.
- **Pas de ré-entraînement automatique**. L'utilisateur doit penser à
  relancer `ml-pollution train` régulièrement.
- **Modèle non versionné** : un seul `.joblib` à la fois. Pour de la
  vraie MLOps, il faudrait un registry (MLflow, DVC...).

## Évolutions futures

- **Cron de ré-entraînement** : workflow GitHub Actions hebdo
- **Plus d'horizons** : prédire H+1, H+3, H+6, H+12
- **Variables exogènes** : jours fériés, événements parisiens (grèves,
  manifestations), émissions industrielles
- **Comparer XGBoost vs LSTM** pour les longues séquences
- **Cross-validation glissante** au lieu de simple split chronologique
