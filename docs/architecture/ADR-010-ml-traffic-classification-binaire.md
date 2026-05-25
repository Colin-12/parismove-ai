# ADR-010 — Classification binaire de perturbations pour ml-traffic

## Statut

Accepté — 22 mai 2026

## Contexte

Le projet ParisMove AI prévoit (Phase 6c) un modèle ML de prédiction des
retards de transports IDFM. L'analyse exploratoire des données (EDA v2,
voir `services/ml-traffic/notebooks/eda_traffic_v2.ipynb`) a révélé que :

1. La distribution des retards est extrêmement déséquilibrée : 83.5% des
   passages ont un retard de exactement 0 seconde.
2. Les lags temporels (h1, h6, h24, h168) ont des corrélations très faibles
   avec la valeur du retard à H+3 (toutes inférieures à 0.06).
3. Les variables météo n'ont aucun signal détectable dans la fenêtre de
   données disponible (~28 jours).
4. Le seul signal robuste est la différence entre modes : les bus ont 3 à
   10 fois plus de retard que le rail.

L'approche initialement scopée — régression du retard moyen à H+3 par ligne
— n'est pas viable avec ces données. Un modèle de régression aurait des
performances marginalement supérieures au baseline trivial "prédire 0".

## Décision

Nous reformulons le problème en **classification binaire** :

> Pour une ligne donnée à l'heure H, prédire la probabilité qu'il y ait
> une perturbation à l'heure H+1.

### Définition de la cible

Une heure est dite **perturbée** si au moins une des conditions est vraie :

1. Au moins 1 passage avec retard > 120s (incident sévère isolé)
2. Au moins 2 passages avec retard > 60s (saturation répétée)

Ces seuils sont configurables dans `ml_traffic.config.Settings`
(`severe_delay_threshold_s`, `delay_threshold_s`, `severe_count_threshold`).

### Stratégie d'entraînement

- **Un seul modèle global** avec `line_id` et `mode` comme features
  catégorielles (cohérent avec ADR-009 sur ml-pollution).
- **Filtre des lignes** : minimum 200 passages historiques pour qu'une
  ligne soit éligible (couvre 98.4% des passages sur 14 lignes).
- **Split chronologique 70/15/15** train/val/test.
- **Pas de feature météo** ni de lag h6/h24/h168 (signaux non détectables
  selon l'EDA v2).
- Feature `lag_h1` à tester en PR XGBoost ; conservée seulement si gain
  démontré.

### Features finales

| Feature | Type | Source |
|---------|------|--------|
| `line_id` | catégorielle | `stop_visits.line_id` |
| `mode` | catégorielle | `idfm_lines.transport_mode` (fallback `stop_visits.transport_mode`) |
| `hour` | numérique (0-23) | `EXTRACT(HOUR FROM recorded_at)` |
| `dow` | numérique (0-6) | `EXTRACT(DOW FROM recorded_at)` |
| `lag_h1` | numérique | `delay_mean` à H-1 (optionnel) |

### Algorithmes

1. **Baseline** : régression logistique scikit-learn (PR `feat/ml-traffic-baseline`)
2. **XGBoost** : seulement si la baseline atteint au moins 70% d'accuracy
   (PR `feat/ml-traffic-xgboost`)

## Conséquences

### Positives

- Approche cohérente avec ADR-009 (XGBoost global avec entité catégorielle).
- Sortie probabiliste exploitable par le coach IA et le dashboard.
- Évaluation honnête : on documente les limites du dataset et adapte le
  scope plutôt que de présenter un modèle peu performant.

### Négatives

- Perte de granularité : on prédit "perturbé oui/non" plutôt qu'un retard
  exact en secondes. Acceptable pour l'usage métier (alerte utilisateur).
- Horizon réduit à H+1 (vs H+3 initialement prévu). Acceptable car les
  lags h3 n'ont pas montré de pouvoir prédictif.
- Le modèle ne sera entraîné que sur 14 lignes éligibles (sur ~2 100 lignes
  IDFM). À documenter clairement.

## Alternatives écartées

1. **Régression du retard moyen à H+3** : non viable, baseline trivial trop fort.
2. **Modèle par ligne (14 modèles indépendants)** : sur-ingénierie, données
   insuffisantes par ligne pour XGBoost.
3. **Deux modèles séparés (bus / rail)** : déjà capturé via la feature `mode`,
   doublerait la maintenance pour un gain marginal.
4. **Time-series cross-validation 5 folds** : rigoureux mais surdimensionné
   pour le budget temps avant soutenance.

## Références

- EDA v2 : `services/ml-traffic/notebooks/eda_traffic_v2.ipynb`
- ADR-009 : ML pollution XGBoost global avec station_id catégoriel
- Issue de cadrage : conversation Claude du 22 mai 2026
