# ParisMove AI

> **L'assistant de mobilité qui te fait gagner du temps et préserve ta santé.**
> Prédiction de durée réelle des trajets, score d'exposition à la pollution et coach conversationnel, le tout basé sur les données ouvertes d'Île-de-France.

<p align="left">
  <img alt="Python" src="https://img.shields.io/badge/python-3.11-blue.svg">
  <img alt="Licence" src="https://img.shields.io/badge/licence-MIT-green.svg">
  <img alt="Statut" src="https://img.shields.io/badge/statut-en%20développement-orange.svg">
  <img alt="Deploy" src="https://img.shields.io/badge/deploy-Streamlit%20Cloud-FF4B4B">
</p>

---

## Démo

| Composant | Lien |
|---|---|
| Dashboard utilisateur | _(à venir : lien Streamlit Cloud)_ |
| API publique | _(à venir : lien Render / Railway)_ |
| Vidéo de démo (15-20 min) | _(à venir : lien YouTube non répertorié)_ |

![Capture du dashboard](docs/screenshot.png)

---

## Problème résolu

Les applications de mobilité existantes (Google Maps, Citymapper, IDFM) donnent l'**horaire théorique** des transports. En réalité :

- Un RER B à 18h est en retard moyen de 4 à 7 minutes selon la saison et la météo.
- Un trajet à vélo entre Châtelet et La Défense expose à des pics de NO₂ supérieurs aux seuils OMS un jour sur trois.
- Aucun outil ne combine **prédiction de durée réelle**, **exposition à la pollution** et **recommandation personnalisée** en une seule interface.

ParisMove AI répond à ces trois manques avec un produit unifié, construit à 100 % sur des données ouvertes et déployé sur une infrastructure cloud gratuite.

---

## Fonctionnalités

### 1. Trajet optimal prédictif
Modèle `XGBoost` entraîné sur l'historique des perturbations IDFM, la météo et le jour de la semaine pour prédire la **durée réellement vécue** d'un trajet. Métrique de référence : MAE en minutes vs horaire théorique.

### 2. Score Santé Trajet
Calcul d'exposition cumulée aux polluants atmosphériques (PM2.5, NO₂, O₃) le long d'un itinéraire, en intégrant les données Airparif / AQICN. Particulièrement utile pour les trajets à vélo, à pied ou en running.

### 3. Coach Mobilité (RAG + LLM)
Agent conversationnel basé sur une architecture RAG (Groq + LangChain + ChromaDB). Répond à des requêtes en langage naturel du type :

> _« Je pars de Châtelet pour La Défense dans 20 minutes, j'ai de l'asthme, que dois-je faire ? »_

Le coach combine les prédictions du pipeline ML et les données temps réel pour fournir une recommandation chiffrée et justifiée.

---

## Architecture

```
┌─────────────────┐    ┌───────────────────┐    ┌────────────────────┐
│  Sources data   │───▶│  Pipeline & ML    │───▶│  Produit utilisateur│
│                 │    │                   │    │                    │
│ • PRIM IDFM     │    │ • GitHub Actions  │    │ • Streamlit Cloud  │
│ • AQICN/Atmo    │    │ • Supabase PG     │    │ • FastAPI (Render) │
│ • Open-Meteo    │    │ • XGBoost/Prophet │    │ • Coach RAG (Groq) │
│ • data.gouv.fr  │    │ • MLflow local    │    │                    │
└─────────────────┘    └───────────────────┘    └────────────────────┘
```

Détails complets dans [`docs/architecture/ARCHITECTURE.md`](docs/architecture/ARCHITECTURE.md).

---

## Stack technique

| Couche | Choix | Pourquoi |
|---|---|---|
| **Ingestion** | Python 3.11, `httpx`, `pandas` | Clients async performants pour APIs temps réel |
| **Orchestration** | GitHub Actions (cron) | Gratuit, versionné, pas de serveur à maintenir |
| **Stockage** | Supabase (PostgreSQL + PostGIS) | Free tier 500 Mo, SQL géospatial, API REST auto |
| **ML** | XGBoost, Prophet, scikit-learn | Modèles éprouvés, explicables, entraînables sur CPU |
| **API** | FastAPI, Pydantic | Typing strict, doc OpenAPI auto, async natif |
| **Dashboard** | Streamlit + Folium / Pydeck | Prototypage rapide, rendu cartographique riche |
| **Coach (RAG)** | LangChain, Groq, HuggingFace embeddings, ChromaDB | Latence faible (Groq), stack maîtrisée |
| **Déploiement** | Streamlit Cloud, Render, Supabase | 3 free tiers complémentaires, zéro coût |
| **Observabilité** | Logging structuré (`structlog`) | Traces JSON agrégeables facilement |

**Coût mensuel d'exploitation : 0 €.**

---

## Sources de données

| Source | Données | Licence | Fréquence |
|---|---|---|---|
| [PRIM IDFM](https://prim.iledefrance-mobilites.fr/) | Prochains passages, perturbations, référentiel arrêts | ODbL / Licence Mobilité | Temps réel |
| [AQICN](https://aqicn.org/api/) | Qualité de l'air par station | CC BY-NC | 1 h |
| [Atmo Data](https://www.atmo-france.org/) | Indices pollution agrégés France | ODbL | 1 h |
| [Open-Meteo](https://open-meteo.com/) | Météo, pollution atmosphérique | CC BY | 15 min |
| [data.gouv.fr — Vélib'](https://www.data.gouv.fr/) | Disponibilité stations Vélib' | ODbL | 1 min |

Toutes les sources sont gratuites et conformes RGPD (aucune donnée personnelle collectée).

---

## Structure du repo

```
parismove-ai/
├── services/
│   ├── ingestion/      # Clients API, ETL, chargement en base
│   ├── ml/             # Feature engineering, entraînement, évaluation
│   ├── api/            # FastAPI exposant les prédictions
│   ├── dashboard/      # Streamlit (carte, KPIs, simulation)
│   └── coach/          # Agent RAG conversationnel
├── shared/             # Schémas Pydantic, utilitaires communs
├── infrastructure/     # Configs Supabase, secrets templates, Docker
├── docs/
│   ├── architecture/   # ADRs, schémas C4, décisions techniques
│   └── api/            # Documentation utilisateur et développeur
├── .github/workflows/  # CI, tests, ingestion planifiée
└── scripts/            # Bootstrap, migration, batch utilities
```

---

## Démarrage rapide

### Prérequis
- Python 3.11+
- Un compte Supabase (free tier)
- Une clé API [PRIM IDFM](https://prim.iledefrance-mobilites.fr/fr/compte/api-key) (gratuite)
- Une clé API [AQICN](https://aqicn.org/data-platform/token/) (gratuite)
- Une clé API [Groq](https://console.groq.com/) (gratuite, pour le coach)

### Installation locale

```bash
git clone https://github.com/Colin-12/parismove-ai.git
cd parismove-ai

# Environnement virtuel
python -m venv .venv
source .venv/bin/activate   # Windows : .venv\Scripts\activate

# Dépendances (installe les services en mode éditable)
pip install -e "services/ingestion[dev]"
pip install -e "services/ml[dev]"
pip install -e "services/api[dev]"

# Variables d'environnement
cp infrastructure/.env.example .env
# Édite .env avec tes clés API

# Lancement d'une ingestion locale
python -m ingestion.run --source prim --since 1h

# Lancement de l'API
uvicorn api.main:app --reload

# Lancement du dashboard
streamlit run services/dashboard/app.py
```

---

## Planning

Projet piloté en méthodologie agile (sprints de 2 semaines). Détail complet dans [`docs/PLANNING.md`](docs/PLANNING.md).

| Phase | Durée | Livrables |
|---|---|---|
| **1. Cadrage** | Semaines 1-2 | Cahier des charges affiné, ADRs initiaux |
| **2. Ingestion & stockage** | Semaines 3-6 | Pipeline ETL opérationnel, BDD historisée |
| **3. ML & prédiction** | Semaines 7-12 | Modèles entraînés, métriques validées |
| **4. Produit utilisateur** | Semaines 13-18 | Dashboard + API + coach livrés |
| **5. Polissage & livraison** | Semaines 19-24 | Vidéo, documentation finale, soutenance |

---

## Évaluation des modèles ML

| Modèle | Objectif | Métrique cible |
|---|---|---|
| Prédicteur de durée de trajet | Estimation temps réel vs horaire théorique | MAE < 3 min |
| Prédicteur de pic de pollution | Classification binaire dépassement seuil OMS | F1 > 0.75, AUC > 0.80 |
| Modèle de scoring santé | Régression exposition cumulée | R² > 0.70 |

Résultats détaillés et matrices de confusion : [`docs/ml/EVALUATION.md`](docs/ml/EVALUATION.md).

---

## Tests et qualité

- Tests unitaires : `pytest` (couverture cible > 70 %)
- Linting : `ruff`, `mypy` en mode strict
- CI : GitHub Actions sur chaque PR
- Pre-commit hooks : formatage, type-check, tests rapides

```bash
# Exécuter les tests
pytest

# Vérifier la qualité du code
ruff check .
mypy services/
```

---

## Contexte académique

Projet réalisé dans le cadre du **Mastère 2 Big Data & IA — Sup de Vinci** (promo 2025-2026).
Cahier des charges : « Optimisation de la mobilité urbaine à l'aide des données ouvertes ».

Ce repo constitue le livrable technique du projet d'étude. Le rendu officiel inclut également :
- Un document technique final (PDF)
- Une vidéo de démonstration de 15 à 20 minutes
- Une analyse individuelle par membre de l'équipe

---

## Auteur

**Colin** — AI / Data Engineer
[github.com/Colin-12](https://github.com/Colin-12) · [Portfolio](https://github.com/Colin-12/portfolio)

---

## Licence

Code distribué sous licence [MIT](LICENSE).
Données sources sous leurs licences respectives (ODbL, CC BY, Licence Mobilité) — voir la section *Sources de données*.
