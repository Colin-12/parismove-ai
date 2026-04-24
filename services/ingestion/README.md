# Service : Ingestion

Collecte les données des APIs ouvertes (PRIM IDFM, AQICN, Open-Meteo, data.gouv.fr) et les charge dans Supabase.

## Responsabilités

- Appeler les APIs avec gestion des quotas et retry exponentiel (`tenacity`)
- Normaliser les données au format `shared.schemas` (Pydantic)
- Historiser dans PostgreSQL (tables `raw_*` brutes, `stg_*` transformées)
- Produire des logs structurés JSON pour observabilité

## Structure

```
src/ingestion/
├── __init__.py
├── cli.py              # Point d'entrée Click
├── config.py           # Settings Pydantic (lecture .env)
├── clients/            # Un client par source
│   ├── prim.py
│   ├── aqicn.py
│   ├── meteo.py
│   └── velib.py
├── transformers/       # Normalisation brut → modèle
├── loaders/            # Écriture en base
└── run.py              # Orchestrateur principal
```

## Exécution

```bash
# Ingestion d'une source précise
python -m ingestion.cli run --source prim --since 1h

# Ingestion complète
python -m ingestion.cli run --source all

# Mode dry-run (logs sans écriture)
python -m ingestion.cli run --source prim --dry-run
```

## Tests

```bash
pytest tests/
pytest tests/test_prim_client.py -v
```

## Déploiement

Exécuté par GitHub Actions toutes les 15 minutes (voir `.github/workflows/ingestion.yml`).
