# ParisMove AI

> Système de monitoring temps-réel de la mobilité francilienne avec assistant IA conversationnel et prédiction de pollution PM2.5.

<p align="left">
  <img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-blue.svg">
  <img alt="Postgres" src="https://img.shields.io/badge/postgres-Supabase-336791">
  <img alt="Streamlit" src="https://img.shields.io/badge/streamlit-Cloud-FF4B4B">
  <img alt="LLM" src="https://img.shields.io/badge/LLM-Groq%20%7C%20LLaMA%203.3-orange">
  <img alt="ML" src="https://img.shields.io/badge/ML-XGBoost-009688">
  <img alt="Tests" src="https://img.shields.io/badge/tests-280%2B-brightgreen">
  <img alt="Licence" src="https://img.shields.io/badge/licence-MIT-green">
</p>

---

## 🌐 Démo en ligne

**Dashboard public** : [parismove-ai.streamlit.app](https://parismove-ai.streamlit.app)

5 modules interactifs accessibles publiquement :
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

Monorepo Python avec **6 services autonomes** :

```
parismove-ai/
├── shared/                       Modèles Pydantic + helpers BDD
├── services/
│   ├── ingestion/                Pipeline ETL (3 sources, cron 30min)
│   ├── healthscore/              Score santé A-E multicritère
│   ├── coach/                    Coach IA RAG data-aware
│   ├── ml-pollution/             Modèle XGBoost prédiction PM2.5
│   └── dashboard/                Streamlit 5 pages
├── docs/architecture/            ADRs (9 décisions documentées)
├── infrastructure/migrations/    Migrations SQL Supabase
└── .github/workflows/            CI + cron d'ingestion
```

### Flux de données

```
┌────────────────┐    ┌─────────────────────────┐    ┌────────────────┐
│  PRIM IDFM     │───►│                         │    │                │
├────────────────┤    │   Ingestion service     │    │   Dashboard    │
│  AQICN/Airparif│───►│   (cron 30 min,         │───►│   Streamlit    │
├────────────────┤    │    GitHub Actions)      │    │   (5 pages)    │
│  Open-Meteo    │───►│                         │    │                │
└────────────────┘    └─────────────┬───────────┘    └────┬───────────┘
                                    │                     │
                                    ▼                     │
                           ┌─────────────────┐            │
                           │  PostgreSQL     │            │
                           │  Supabase       │◄───────────┘
                           │  (star schema)  │            │
                           └────────┬────────┘            │
                                    │                     │
                ┌───────────────────┼─────────────────────┤
                ▼                   ▼                     ▼
        ┌──────────────┐    ┌──────────────┐      ┌───────────────┐
        │ Healthscore  │    │  Coach IA    │      │ ML pollution  │
        │ (scoring A-E)│    │  (Groq+LLaMA)│      │ (XGBoost)     │
        └──────────────┘    └──────────────┘      └───────────────┘
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

9 décisions importantes sont documentées dans `docs/architecture/` :

- **ADR-001** — Choix de Supabase (PostgreSQL managé)
- **ADR-002** — psycopg 3 + NullPool + `prepare_threshold=None` (fix DuplicatePreparedStatement avec le pooler Supabase)
- **ADR-003** — Star schema, enrichissement par JOIN
- **ADR-004** — Healthscore A-E avec pondération 60/30/10 (Pollution/Météo/Trafic)
- **ADR-005** — Coach RAG data-aware avec LLM-as-controller + 5 tools, anti-hallucination 3 niveaux
- **ADR-006** — Robustesse de l'ingestion : 8 stations Airparif vérifiées + garde géographique
- **ADR-007** — Dashboard Streamlit comme service indépendant
- **ADR-008** — Pages Trafic + Score santé interactif
- **ADR-009** — Modèle ML XGBoost global avec station_id catégoriel

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
- **Stations** : 8 stations Airparif en IDF, sélectionnées et géo-vérifiées
  (Paris centre, Paris 1er Les Halles, Paris 18ème, La Défense, Gennevilliers, Bobigny, Vitry-sur-Seine, Cergy-Pontoise)

### Open-Meteo
- **API** : [open-meteo.com](https://open-meteo.com)
- **Données** : météo (température, humidité, vent, pluie) sur 10 points IDF

---

## 🚀 Démarrage rapide

### Pré-requis

- Python 3.11 ou 3.12
- Compte Supabase (Free tier) avec une base PostgreSQL
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

# Installation des 6 packages en mode editable
pip install -e shared
pip install -e services/ingestion
pip install -e services/healthscore
pip install -e services/coach
pip install -e services/ml-pollution
pip install -e services/dashboard

# Outils de qualité (optionnel)
pip install ruff mypy pytest pytest-cov
```

### Configuration

Créer un fichier `.env` à la racine :

```bash
# Base de données Supabase
DATABASE_URL=postgresql+psycopg://postgres.xxxxx:PASSWORD@aws-0-eu-west-1.pooler.supabase.com:6543/postgres

# APIs
PRIM_API_KEY=xxxxx
AQICN_TOKEN=xxxxx
GROQ_API_KEY=gsk_xxxxx
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_MODEL_SMALL=llama-3.1-8b-instant
```

Appliquer les migrations SQL :

```bash
# Les fichiers .sql sont dans infrastructure/migrations/
# À exécuter dans l'éditeur SQL de Supabase
```

### Utilisation

```bash
# Ingérer les données (toutes sources)
python -m ingestion.cli run --source all --store

# Calculer un score santé pour un trajet
healthscore score \
    --journey-id rer-a \
    --label "RER A Châtelet → La Défense" \
    --point 48.8585,2.3470 \
    --point 48.8918,2.2389

# Discuter avec le coach IA
coach ask "Comment est l'air à Paris en ce moment ?"

# Entraîner le modèle ML
ml-pollution train --days 30
ml-pollution predict @5722

# Lancer le dashboard
streamlit run services/dashboard/src/dashboard/app.py
```

---

## 🧪 Tests

Le projet compte **280+ tests** automatisés couvrant :

- Clients API (PRIM, AQICN, Open-Meteo) avec mocks httpx
- Transformers et loaders (validation Pydantic, déduplication)
- Logique de scoring (multi-critères, seuils OMS)
- Coach IA (intent classification, orchestrator, anti-hallucination)
- Modèle ML (features, persistence, split chronologique)
- Pages dashboard (tests structurels)

```bash
# Lancer tous les tests
pytest services/

# Avec couverture
pytest services/ --cov=services --cov-report=term-missing
```

CI verte sur chaque push grâce à `.github/workflows/ci.yml` (Ruff + Mypy + Pytest sur tous les services).

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
   │     prompt système avec règles strictes
   │     + données du tool (CONTEXTE)
        │
        ▼
   Réponse formatée :
   🟢/🟡/🟠/🔴 Sujet : X/10 (qualificatif)
   Nuance + conseil actionnable
   Source : XXX, mesuré il y a Xh
```

### Anti-hallucination en 3 niveaux

1. **Forcing tools** : si l'intent matche, le LLM DOIT appeler le tool, pas répondre depuis sa connaissance générale
2. **Citations sources obligatoires** : tout chiffre doit venir d'un tool result, sinon refus
3. **Mode warning ⚠️** : si pas de tool result disponible, la réponse commence obligatoirement par "⚠️ Pas de données temps-réel..."

### Bilingue automatique

Détection FR/EN du message utilisateur, réponse dans la même langue, jamais de mélange.

---

## 📈 Modèle ML pollution — Détails

**Cible** : prédiction PM2.5 à H+1 sur les 8 stations Airparif IDF.

**Approche** : 1 modèle global XGBoost avec `station_id` comme feature catégorielle (encodage natif via `enable_categorical=True`).

**Features (10)** :

| Catégorie | Features |
|-----------|----------|
| Temporelles | `heure`, `jour_semaine`, `mois` |
| Lag PM2.5 | `pm25_h1` (il y a 1h), `pm25_h24` (il y a 24h) |
| Météo | `temperature_c`, `humidity_pct`, `wind_speed_ms`, `precipitation_mm` |
| Géographique | `station_id` (catégoriel) |

**Validation** : split chronologique 80/20 (pas aléatoire — éviter la fuite temporelle sur séries temporelles).

**Inspiration** : [OptiMobility-BDIA-2025](https://github.com/Colin-12/OptiMobility-BDIA-2025) (projet personnel antérieur), amélioré ici avec multi-stations + features météo + architecture monorepo + tests.

---

## 📦 Déploiement

### Streamlit Cloud (dashboard)

Le dashboard est déployé sur [Streamlit Community Cloud](https://share.streamlit.io) :

- Branche surveillée : `develop`
- Entry point : `services/dashboard/src/dashboard/app.py`
- Secrets configurés via l'UI Streamlit Cloud
- Redéploiement automatique à chaque push

### GitHub Actions (ingestion)

Workflow `.github/workflows/ingestion.yml` :

```yaml
on:
  schedule:
    - cron: "*/30 * * * *"   # Toutes les 30 minutes
  workflow_dispatch:          # Trigger manuel possible
```

Exécute `python -m ingestion.cli run --source all --store` qui ingère les 3 sources et écrit dans Supabase.

### Coûts

Le projet est **100% gratuit** grâce aux free tiers :
- Supabase Free : 500 Mo de BDD, 2 Go de bande passante
- Streamlit Cloud : 1 app publique avec 1 Go de RAM
- Groq Free : ~6 000 requêtes/min en burst, gratuit pour usage personnel
- GitHub Actions Free : 2 000 minutes/mois (largement suffisant pour le cron)

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
│   │       ├── scoring.py                   # Aggrégation A-E
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
│   ├── ml-pollution/                        # Service ML
│   │   └── src/ml_pollution/
│   │       ├── data_access.py               # Fetch + jointure météo
│   │       ├── features.py                  # Feature engineering
│   │       ├── train.py                     # Entraînement XGBoost
│   │       ├── predict.py                   # Inférence + backtest
│   │       └── persistence.py               # joblib + meta JSON
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
├── docs/architecture/                       # 9 ADRs
├── infrastructure/migrations/               # SQL Supabase
└── .github/workflows/                       # CI + cron
```

---

## 🎓 Contexte du projet

Projet de fin d'études du **Mastère 2 Big Data & IA** à [Sup de Vinci](https://www.supdevinci.fr/) (campus Brest), réalisé en alternance chez Eureden.

### Compétences mises en œuvre

- **Data Engineering** : pipeline ETL multi-sources, ingestion temps-réel via API REST, modélisation star schema, dédoublonnage, qualité de données
- **Cloud / DevOps** : déploiement multi-service, GitHub Actions (CI + cron), gestion de secrets, monorepo Python avec packages éditables
- **Machine Learning** : feature engineering, validation chronologique, persistance modèle, inference batch + temps-réel, MLOps minimaliste
- **IA Générative / RAG** : LLM-as-controller, tools data-aware, prompt engineering, anti-hallucination, intent classification
- **Frontend / Dataviz** : Streamlit multi-page, cartes Folium, graphes Plotly, theme custom, cache stratégique
- **Backend** : architecture microservice, Pydantic strict, API design (CLI), gestion d'erreurs robuste
- **Qualité logicielle** : 280+ tests, type checking strict, ADRs, documentation

---

## 📝 Licence

MIT — voir [LICENSE](LICENSE).

---

## 👤 Auteur

**Colin Komtcheu (Armand)**
Mastère 2 Big Data & IA, Sup de Vinci · Brest

- 🔗 [LinkedIn](linkedin.com/in/armand-colin-komtcheu-0014471b3)
- 💻 [GitHub](https://github.com/Colin-12)
- 🌐 [Portfolio](https://github.com/Colin-12/portfolio)

Ouvert aux opportunités CDI Bretagne / Grand Ouest sur des postes Data Analyst, Data Scientist ou MLOps.

---

## 🙏 Remerciements

- [Île-de-France Mobilités](https://prim.iledefrance-mobilites.fr) pour l'ouverture des données PRIM
- [Airparif](https://www.airparif.asso.fr) et [AQICN](https://aqicn.org) pour les données de qualité de l'air
- [Open-Meteo](https://open-meteo.com) pour les données météo gratuites et fiables
- [Groq](https://groq.com) pour l'inférence LLaMA ultra-rapide gratuite
- [Supabase](https://supabase.com) et [Streamlit](https://streamlit.io) pour les free tiers généreux
