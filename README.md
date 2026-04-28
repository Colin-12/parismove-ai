# ParisMove AI

> L'assistant mobilité qui te fait gagner du temps et préserve ta santé.

Pipeline de données et services d'analyse pour la mobilité urbaine en Île-de-France.
Combine transports en commun (PRIM IDFM), qualité de l'air (AQICN, Open-Meteo) et
météo pour aider à choisir le meilleur trajet.

**Statut** : projet étudiant en cours (Mastère 2 Big Data & IA, Sup de Vinci).

## Aperçu de l'architecture

```
┌──────────────────────────────────────────────────────────────┐
│                  Sources de données ouvertes                 │
├──────────────────┬──────────────────┬───────────────────────┤
│   PRIM IDFM      │     AQICN        │     Open-Meteo        │
│  (transports)    │  (qualité air)   │  (météo + air modèle) │
└──────────────────┴──────────────────┴───────────────────────┘
                            │
                            ▼
                  ┌───────────────────┐
                  │   Ingestion       │  Cron GitHub Actions
                  │   (cron 30 min)   │  toutes les 30 min
                  └─────────┬─────────┘
                            │
                            ▼
                  ┌───────────────────┐
                  │   Supabase        │  PostgreSQL 17 cloud
                  │   PostgreSQL      │  + référentiel IDFM
                  └─────────┬─────────┘
                            │
                ┌───────────┴────────────┐
                ▼                        ▼
       ┌────────────────┐       ┌────────────────┐
       │  Healthscore   │       │   Dashboard    │
       │  (score A-E)   │       │  (à venir)     │
       └────────────────┘       └────────────────┘
```

## Services

| Service | Rôle | Statut |
|---|---|---|
| `services/ingestion` | Collecte 3 sources de données | ✅ En production |
| `services/healthscore` | Score santé de trajets | ✅ MVP |
| `services/dashboard` | Visualisation Streamlit | 🚧 À venir |
| `services/coach` | Assistant LLM (RAG) | 🚧 À venir |

## Démarrage rapide

### Prérequis
- Python 3.11+
- Compte Supabase (gratuit)
- Clé API PRIM IDFM (gratuite, [inscription](https://prim.iledefrance-mobilites.fr/))
- Token AQICN (gratuit, [inscription](https://aqicn.org/data-platform/token/))

### Installation

```bash
git clone https://github.com/Colin-12/parismove-ai
cd parismove-ai

python -m venv .venv
source .venv/bin/activate     # Linux/macOS
.venv\Scripts\activate        # Windows

pip install -e shared
pip install -e services/ingestion
pip install -e services/healthscore
```

### Configuration

Copier `infrastructure/.env.example` en `.env` à la racine et renseigner :
- `PRIM_API_KEY` — clé PRIM IDFM
- `AQICN_TOKEN`  — token AQICN
- `DATABASE_URL` — chaîne Supabase au format `postgresql+psycopg://...`

### Initialisation de la base

Appliquer les migrations dans Supabase SQL Editor, dans l'ordre :
- `infrastructure/migrations/001_create_stop_visits.sql`
- `infrastructure/migrations/002_create_air_measurements.sql`
- `infrastructure/migrations/003_create_weather_observations.sql`
- `infrastructure/migrations/004_create_idfm_lines.sql`

Puis charger le référentiel IDFM :

```bash
python -m ingestion.cli refresh-references
```

### Utilisation

**Lancer une ingestion ponctuelle :**

```bash
python -m ingestion.cli run --source all --store
```

**Calculer le score santé d'un trajet :**

```bash
healthscore score \
    --journey-id rer-a \
    --label "RER A Châtelet → La Défense" \
    --point 48.8585,2.3470 \
    --point 48.8918,2.2389
```

**Comparer deux trajets :**

```bash
healthscore compare \
    --journey "rer-a:RER A:48.8585,2.3470:48.8918,2.2389" \
    --journey "metro-1:Métro 1:48.8585,2.3470:48.8718,2.2900:48.8918,2.2389"
```

## Décisions d'architecture (ADR)

Les choix techniques majeurs sont documentés dans `docs/architecture/` :
- ADR-001 : Choix de Supabase comme backend de stockage
- ADR-002 : Driver PostgreSQL (psycopg 3) et stratégie de pooling
- ADR-003 : Modèle dimensionnel star schema pour l'enrichissement
- ADR-004 : Calcul du score santé multicritère

## Tests

```bash
pytest services/ingestion
pytest services/healthscore
```

## CI/CD

GitHub Actions exécute à chaque PR :
- `ruff check` (linting)
- `mypy` (type checking strict)
- `pytest` (tests unitaires)

Le cron d'ingestion s'exécute automatiquement toutes les 30 minutes en production.

## Licence et contributeurs

Projet étudiant — Colin Komtcheu, Mastère 2 Big Data & IA, Sup de Vinci.
