# ParisMove AI

> Système de monitoring temps-réel de la mobilité francilienne avec assistant IA conversationnel et prédiction de pollution PM2.5.

<p align="left">
  <img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-blue.svg">
  <img alt="Postgres" src="https://img.shields.io/badge/postgres-Supabase-336791">
  <img alt="Streamlit" src="https://img.shields.io/badge/streamlit-Cloud-FF4B4B">
  <img alt="LLM" src="https://img.shields.io/badge/LLM-Groq%20%7C%20LLaMA%203.3-orange">
  <img alt="ML" src="https://img.shields.io/badge/ML-XGBoost-009688">
  <img alt="Tests" src="https://img.shields.io/badge/tests-300%2B-brightgreen">
  <img alt="Licence" src="https://img.shields.io/badge/licence-MIT-green">
</p>

---

## 🌐 Démo en ligne

**Dashboard public** : [parismove-ai.streamlit.app](https://parismove-ai.streamlit.app)

6 modules interactifs accessibles publiquement :
- 🏠 **Accueil** — KPIs globaux et historique d'ingestion
- 🌫️ **Qualité de l'air** — Carte Folium des stations Airparif, tendances 48h
- 🤖 **Coach IA** — Chat conversationnel data-aware (Groq + LLaMA)
- 🚇 **Trafic** — Heatmap des retards, top lignes les plus en retard
- 🌿 **Score santé** — Calculateur de trajet avec note A-E
- 🔮 **Prévision air** — Modèle XGBoost pour prédire le PM2.5 à H+1

---

## 🎯 Problème résolu

Les applications de mobilité grand public (Google Maps, Citymapper, IDFM) donnent l'**horaire théorique** des transports. Mais en réalité :

- 30 % des passages RATP/SNCF arrivent avec un **retard significatif** (>1 min)
- Les zones IDF ont des **niveaux de pollution PM2.5 très différents** (Cergy 30 µg/m³ vs Paris Halles 90 µg/m³)
- Aucune appli **ne croise** trafic, qualité de l'air et météo pour évaluer la **qualité d'un trajet**

ParisMove AI ingère ces 3 sources en temps réel, calcule un **score santé multicritère** par trajet, et propose un **coach conversationnel** qui répond aux questions des utilisateurs avec les vraies données.

---

## 🏗️ Architecture

Monorepo Python avec **7 services autonomes** :

```
parismove-ai/
├── shared/                       Modèles Pydantic + helpers BDD
├── services/
│   ├── ingestion/                Pipeline ETL (3 sources, cron 30 min)
│   ├── healthscore/              Score santé A-E multicritère
│   ├── coach/                    Coach IA RAG data-aware
│   ├── ml-pollution/             Modèle XGBoost prédiction PM2.5 H+1
│   ├── ml-traffic/               Modèle XGBoost prédiction perturbations H+1
│   └── dashboard/                Streamlit 6 pages
├── docs/architecture/            11 ADRs documentés
├── infrastructure/migrations/    Migrations SQL Supabase
└── .github/workflows/            CI + cron d'ingestion
```

### Flux de données

```mermaid
flowchart TD
    PRIM[PRIM IDFM] --> ING
    AQICN[AQICN / Airparif] --> ING
    METEO[Open-Meteo] --> ING
    REF[IDFM référentiel] --> ING

    ING["ingestion\nETL cron 30 min · GitHub Actions"]
    ING --> DB

    DB[("PostgreSQL · Supabase\nstop_visits · air_measurements · weather_observations")]

    DB --> HS
    DB --> COACH
    DB --> MLP
    DB --> MLT

    HS["healthscore\nScore A-E trajet"]
    COACH["coach\nLLM data-aware"]
    MLP["ml-pollution\nXGBoost PM2.5 H+1"]
    MLT["ml-traffic\nXGBoost perturbations H+1"]
    SHARED["shared\nPydantic · helpers"]

    GROQ["Groq · LLaMA\n70B + 8B"] -.-> COACH

    HS --> DASH
    COACH --> DASH
    MLP --> DASH
    MLT --> DASH

    DASH["dashboard\nStreamlit · 6 pages · Streamlit Cloud"]
```

---

## 🛠️ Stack technique

| Domaine | Technologies |
|---------|-------------|
| **Langage** | Python 3.11+ avec typage strict (Mypy) |
| **Base de données** | PostgreSQL via [Supabase](https://supabase.com) (Free tier, EU West) |
| **ORM / SQL** | SQLAlchemy 2.0 + psycopg 3 |
| **Modèles de données** | Pydantic v2 |
| **HTTP client** | httpx (async) |
| **Orchestration** | GitHub Actions (CI + cron d'ingestion) |
| **LLM** | [Groq](https://groq.com) — LLaMA 3.3 70B (génération) + 3.1 8B (intent) |
| **ML** | XGBoost 2.0 + scikit-learn |
| **Dashboard** | Streamlit + Plotly + Folium + streamlit-folium |
| **Hébergement dashboard** | [Streamlit Community Cloud](https://streamlit.io/cloud) (gratuit) |
| **Qualité code** | Ruff (lint + format) + Mypy strict + Pytest |

### Choix d'architecture documentés (ADRs)

11 décisions importantes sont documentées dans `docs/architecture/` :

- **ADR-001** — Choix de Supabase (PostgreSQL managé)
- **ADR-002** — psycopg 3 + NullPool + `prepare_threshold=None`
- **ADR-003** — Star schema, enrichissement par JOIN
- **ADR-004** — Healthscore A-E avec pondération 60/30/10 (Pollution/Météo/Trafic)
- **ADR-005** — Coach RAG data-aware avec LLM-as-controller + 5 tools, anti-hallucination 3 niveaux
- **ADR-006** — Robustesse de l'ingestion : 7 stations Airparif vérifiées + garde géographique
- **ADR-007** — Dashboard Streamlit comme service indépendant
- **ADR-008** — Pages Trafic + Score santé interactif
- **ADR-009** — ML pollution XGBoost global avec station_id catégoriel
- **ADR-010** — ML traffic : classification binaire de perturbations H+1
- **ADR-011** — Sélection XGBoost pour ml-traffic (AUC 0.745 vs 0.717 baseline)

---

## 📊 Sources de données

### PRIM IDFM (Île-de-France Mobilités)
- **API** : [prim.iledefrance-mobilites.fr](https://prim.iledefrance-mobilites.fr)
- **Données** : passages temps-réel des transports en commun (Métro, RER, Bus, Tram)
- **Volume** : ~2 000 passages capturés toutes les 30 minutes
- **Référentiel statique** : 2 123 lignes IDFM avec mode et opérateur

### AQICN / Airparif
- **API** : [aqicn.org](https://aqicn.org)
- **Données** : qualité de l'air (AQI, PM2.5, PM10, NO₂, O₃)
- **Stations** : 7 stations Airparif en IDF, sélectionnées et géo-vérifiées

### Open-Meteo
- **API** : [open-meteo.com](https://open-meteo.com)
- **Données** : météo (température, humidité, vent, pluie) sur 10 points IDF

---

## 🚀 Démarrage rapide

### Pré-requis

- Python 3.11 ou 3.12
- Compte [Supabase](https://supabase.com) (Free tier) avec une base PostgreSQL
- Clé API [Groq](https://console.groq.com) (gratuit pour le LLM)
- Token [AQICN](https://aqicn.org/data-platform/token/) (gratuit)
- Clé API [PRIM IDFM](https://prim.iledefrance-mobilites.fr) (gratuit après inscription)

### Installation

```bash
# Clone
git clone https://github.com/Colin-12/parismove-ai.git
cd parismove-ai

# Virtual environment
python -m venv .venv
source .venv/Scripts/activate          # Git Bash Windows
# ou : source .venv/bin/activate       # Linux/Mac

# Installation des 7 packages en mode éditable
pip install -e shared
pip install -e services/ingestion
pip install -e services/healthscore
pip install -e services/coach
pip install -e services/ml-pollution
pip install -e services/ml-traffic
pip install -e services/dashboard
```

### Configuration

Créer un fichier `.env` à la racine :

```env
# Base de données Supabase (Transaction Pooler, port 6543)
DATABASE_URL=postgresql+psycopg://postgres.xxxxx:PASSWORD@aws-0-eu-west-1.pooler.supabase.com:6543/postgres

# APIs externes
PRIM_API_KEY=xxxxx
AQICN_TOKEN=xxxxx
GROQ_API_KEY=gsk_xxxxx
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_MODEL_SMALL=llama-3.1-8b-instant
```

Appliquer les migrations SQL dans l'éditeur SQL de Supabase (fichiers dans `infrastructure/migrations/`, dans l'ordre numérique).

### Utilisation

```bash
# Ingérer les données (toutes sources)
python -m ingestion.cli run --source all --store

# Rafraîchir le référentiel IDFM
python -m ingestion.cli refresh-references

# Calculer un score santé
healthscore score \
    --journey-id chatelet-defense \
    --label "Châtelet → La Défense" \
    --point 48.8585,2.3470 \
    --point 48.8918,2.2389

# Entraîner le modèle ML pollution
python -m ml_pollution.cli train --days 28

# Entraîner et comparer les modèles ML trafic
python -m ml_traffic.cli train
python -m ml_traffic.cli train-xgb
python -m ml_traffic.cli compare

# Lancer le dashboard en local
streamlit run services/dashboard/src/dashboard/app.py
```

---

## 🧪 Tests

```bash
# Lancer tous les tests
pytest services/

# Avec couverture
pytest services/ --cov=services --cov-report=term-missing
```

CI verte sur chaque push via `.github/workflows/ci.yml` (Ruff + Mypy + Pytest sur tous les services).

---

## 🤖 Le Coach IA — Architecture détaillée

Le coach utilise une approche **LLM-as-controller** avec 5 tools data-aware :

```
Question utilisateur
        │
        ▼
[Intent Classifier] ─── LLaMA 3.1 8B (rapide)
        │
        ▼
[Orchestrator] ─── Sélection des tools selon l'intent
        │
        ├──► Tool: get_air_quality(zone)
        ├──► Tool: get_traffic_status(line)
        ├──► Tool: get_weather(zone)
        ├──► Tool: get_health_score(journey)
        └──► Tool: get_capabilities()
        │
        ▼
[Generator] ─── LLaMA 3.3 70B (qualité)
          prompt système avec règles strictes
          + données du tool (CONTEXTE)
        │
        ▼
   Réponse formatée :
   🟢/🟡/🟠/🔴 Sujet : X/10 (qualificatif)
   Nuance + conseil actionnable
   Source : XXX, mesuré il y a Xh
```

**Anti-hallucination en 3 niveaux**

1. **Forcing tools** : si l'intent matche, le LLM DOIT appeler le tool, pas répondre depuis sa connaissance générale
2. **Citations sources obligatoires** : tout chiffre doit venir d'un tool result, sinon refus
3. **Mode warning ⚠️** : si pas de tool result disponible, la réponse commence obligatoirement par "⚠️ Pas de données temps-réel..."

**Bilingue automatique** : détection FR/EN du message utilisateur, réponse dans la même langue, jamais de mélange.

---

## 📈 Modèles ML — Détails

### ML Pollution (PM2.5 H+1)

**Cible** : prédiction PM2.5 à H+1 sur les 7 stations Airparif IDF.

**Approche** : 1 modèle global XGBoost avec `station_id` comme feature catégorielle (`enable_categorical=True`).

| Catégorie | Features |
|-----------|----------|
| Temporelles | `heure`, `jour_semaine`, `mois` |
| Lag PM2.5 | `pm25_h1` (il y a 1h), `pm25_h24` (il y a 24h) |
| Météo | `temperature_c`, `humidity_pct`, `wind_speed_ms`, `precipitation_mm` |
| Géographique | `station_id` (catégoriel) |

**Métriques** : MAE 8.13 µg/m³ · RMSE 11.79 µg/m³ (split chronologique 80/20)

### ML Traffic (perturbations H+1)

**Cible** : prédire si une ligne IDFM sera perturbée (retard > 120s ou ≥ 2 passages > 60s) dans l'heure suivante.

**Approche** : XGBoost binaire global, features `mode`, `line_id`, `hour`, `dow`.

**Métriques** : AUC 0.745 · F1 0.594 · Accuracy 0.654 (split chronologique 70/15/15)

---

## 📦 Déploiement

### Streamlit Cloud (dashboard)

- Branche surveillée : `develop`
- Entry point : `services/dashboard/src/dashboard/app.py`
- Secrets configurés via l'UI Streamlit Cloud
- Redéploiement automatique à chaque push

### GitHub Actions (ingestion)

```yaml
on:
  schedule:
    - cron: "*/30 * * * *"   # Toutes les 30 minutes
  workflow_dispatch:          # Trigger manuel possible
```

### Coûts

Le projet est **100% gratuit** grâce aux free tiers :

| Service | Usage | Limite |
|---------|-------|--------|
| Supabase Free | BDD PostgreSQL | 500 Mo, 2 Go bande passante |
| Streamlit Cloud | Dashboard public | 1 app, 1 Go RAM |
| Groq Free | LLM inférence | ~6 000 req/min en burst |
| GitHub Actions Free | CI + cron | 2 000 min/mois |

---

## 📂 Structure détaillée

```
parismove-ai/
│
├── shared/                                  # Code partagé entre services
│   └── src/shared/
│       ├── db/                              # Engine SQLAlchemy + lookups
│       └── schemas/                         # Modèles Pydantic
│
├── services/
│   ├── ingestion/                           # Service écrivain (cron)
│   │   └── src/ingestion/
│   │       ├── clients/                     # PRIM, AQICN, Meteo
│   │       ├── transformers/                # API → Pydantic
│   │       ├── loaders/                     # Pydantic → Postgres
│   │       └── cli.py                       # CLI : run, refresh-references
│   │
│   ├── healthscore/                         # Service lecteur
│   │   └── src/healthscore/
│   │       ├── pollution.py                 # Sub-score air
│   │       ├── weather.py                   # Sub-score météo
│   │       ├── traffic.py                   # Sub-score trafic
│   │       ├── scoring.py                   # Agrégation A-E
│   │       └── compare.py                   # API publique
│   │
│   ├── coach/                               # Service IA
│   │   └── src/coach/
│   │       ├── intent.py                    # Classifier d'intent
│   │       ├── tools.py                     # 5 tools data-aware
│   │       ├── orchestrator.py              # LLM-as-controller
│   │       ├── prompts.py                   # System prompts FR/EN
│   │       └── llm.py                       # Wrapper Groq
│   │
│   ├── ml-pollution/                        # Service ML pollution
│   │   └── src/ml_pollution/
│   │       ├── data_access.py               # Fetch + jointure météo
│   │       ├── features.py                  # Feature engineering
│   │       ├── train.py                     # Entraînement XGBoost
│   │       ├── predict.py                   # Inférence + backtest
│   │       └── persistence.py               # joblib + meta JSON
│   │
│   ├── ml-traffic/                          # Service ML trafic
│   │   └── src/ml_traffic/
│   │       ├── config.py                    # Settings (seuils, hyperparams)
│   │       ├── data.py                      # Chargement + nettoyage
│   │       ├── features.py                  # Target + features
│   │       ├── train.py                     # Baseline + XGBoost
│   │       ├── predict.py                   # Inférence probabiliste
│   │       └── cli.py                       # train, train-xgb, compare
│   │
│   └── dashboard/                           # Service Streamlit
│       └── src/dashboard/
│           ├── app.py                       # Page Accueil
│           ├── data.py                      # Requêtes BDD + cache
│           ├── theme.py                     # CSS et helpers UI
│           └── pages/
│               ├── 1_Qualite_de_l_air.py
│               ├── 2_Coach_IA.py
│               ├── 3_Trafic.py
│               ├── 4_Score_sante.py
│               └── 5_Prevision_air.py
│
├── docs/architecture/                       # 11 ADRs
├── infrastructure/migrations/               # SQL Supabase
└── .github/workflows/                       # CI + cron
```

---

## 🎓 Contexte du projet

Projet de fin d'études du **Mastère 2 Big Data & IA** à [Sup de Vinci](https://www.supdevinci.fr/) (campus Brest), réalisé en alternance chez Eureden.

**Compétences mises en œuvre** :

- **Data Engineering** : pipeline ETL multi-sources, ingestion temps-réel via API REST, modélisation star schema, dédoublonnage, qualité de données
- **Cloud / DevOps** : déploiement multi-service, GitHub Actions (CI + cron), gestion de secrets, monorepo Python avec packages éditables
- **Machine Learning** : feature engineering, validation chronologique, persistance modèle, inférence batch + temps-réel, MLOps minimaliste
- **IA Générative / RAG** : LLM-as-controller, tools data-aware, prompt engineering, anti-hallucination, intent classification
- **Frontend / Dataviz** : Streamlit multi-page, cartes Folium, graphes Plotly, thème custom, cache stratégique
- **Qualité logicielle** : 300+ tests, type checking strict (Mypy), 11 ADRs, documentation

---

## 📝 Licence

MIT — voir [LICENSE](LICENSE).

---

## 👤 Auteur

**Colin Komtcheu (Armand)**
Mastère 2 Big Data & IA, Sup de Vinci · Brest

- 🔗 [LinkedIn](https://linkedin.com/in/armand-colin-komtcheu-0014471b3)
- 💻 [GitHub](https://github.com/Colin-12)
- 🌐 [Portfolio](https://github.com/Colin-12/portfolio)

Ouvert aux opportunités CDI Bretagne / Grand Ouest — Data Analyst, Data Scientist, MLOps.

---

## 🙏 Remerciements

- [Île-de-France Mobilités](https://prim.iledefrance-mobilites.fr) pour l'ouverture des données PRIM
- [Airparif](https://www.airparif.asso.fr) et [AQICN](https://aqicn.org) pour les données de qualité de l'air
- [Open-Meteo](https://open-meteo.com) pour les données météo gratuites et fiables
- [Groq](https://groq.com) pour l'inférence LLaMA ultra-rapide gratuite
- [Supabase](https://supabase.com) et [Streamlit](https://streamlit.io) pour les free tiers généreux
