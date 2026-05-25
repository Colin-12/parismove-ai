# services/ml-traffic

Service de classification de **perturbations IDFM à H+1**.

## Statut

🚧 **En cours de développement** (Phase 6c du projet).

| PR | État | Description |
|----|------|-------------|
| `feat/ml-traffic-scaffold` | ✅ Cette PR | Structure, config, ADR-010, tests vides |
| `feat/ml-traffic-baseline` | ⏳ Prochaine | Régression logistique, évaluation |
| `feat/ml-traffic-xgboost` | ⏳ Conditionnelle | XGBoost si baseline ≥ 70% accuracy |

## Problème

Prédire, pour une ligne IDFM donnée et une heure H, la probabilité qu'il
y ait au moins une perturbation à H+1.

**Définition perturbation** : au moins 1 passage avec retard > 120s, OU
au moins 2 passages avec retard > 60s.

## Stack

- scikit-learn (baseline)
- XGBoost (à venir)
- pandas / SQLAlchemy / psycopg

## Lancement

```bash
# Installation
pip install -e services/ml-traffic[dev]

# Tests
pytest services/ml-traffic/tests/

# Quality
ruff check services/ml-traffic/src
mypy --config-file services/ml-traffic/pyproject.toml services/ml-traffic/src

# Entraînement (PR baseline)
python -m ml_traffic.cli train
```

## Décisions clés

Voir `docs/architecture/ADR-010-ml-traffic-classification-binaire.md` pour
le détail des choix méthodologiques (sélection de la cible, features,
algorithmes, splits).

## Lien avec les autres services

- **services/ingestion** : alimente `stop_visits` consommé par ce service
- **services/coach** : utilisera `predict_disruption_proba()` comme nouveau tool
- **services/dashboard** : page "Prévision retards" (Phase 9 optionnelle)
