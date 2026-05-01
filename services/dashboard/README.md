# ParisMove AI — Dashboard

Dashboard Streamlit pour visualiser les données collectées par le pipeline
ParisMove AI : qualité de l'air, météo, trafic transports en commun, score
santé de trajets et coach conversationnel.

🌐 **Accessible en ligne :** [https://parismove-ai.streamlit.app](https://parismove-ai.streamlit.app)

## Lancement local

Depuis la racine du projet `parismove-ai/` :

```bash
# Pré-requis : .env configuré (DATABASE_URL, GROQ_API_KEY)
pip install -e services/dashboard

streamlit run services/dashboard/src/dashboard/app.py
```

Le dashboard s'ouvre automatiquement sur `http://localhost:8501`.

## Pages disponibles

- 🏠 **Accueil** : KPIs globaux et historique d'ingestion
- 🌫️ **Qualité de l'air** : carte des stations Airparif + tendances 48h
- 🤖 **Coach IA** : assistant conversationnel data-aware (Groq + LLaMA)

À venir :
- 🚇 Trafic transports
- 🌿 Score santé de trajets

## Coach IA

La page Coach réutilise 100% du service `coach` (orchestrateur + tools
data-aware + 3 niveaux d'anti-hallucination). Permet de poser des
questions en langage naturel sur :

- Qualité de l'air (Airparif via AQICN)
- Météo (Open-Meteo)
- Trafic des transports (PRIM IDFM)
- Capacités générales du système

Le coach détecte automatiquement la langue (FR/EN) et préfixe ses
réponses par ⚠️ quand il n'a pas de données temps réel disponibles.

## Déploiement sur Streamlit Cloud

1. Inscription sur [https://streamlit.io/cloud](https://streamlit.io/cloud) avec GitHub
2. **New app** → choisir le repo `parismove-ai`
3. Branche : `develop` (déploiement continu)
4. Main file path : `services/dashboard/src/dashboard/app.py`
5. **Advanced settings → Secrets** :
   ```toml
   DATABASE_URL = "postgresql+psycopg://..."
   GROQ_API_KEY = "gsk_..."
   GROQ_MODEL = "llama-3.3-70b-versatile"
   GROQ_MODEL_SMALL = "llama-3.1-8b-instant"
   ```
6. **Deploy**

Streamlit Cloud lit `requirements.txt` à la racine et installe les
packages internes du monorepo en mode editable.

## Architecture

```
services/dashboard/
├── pyproject.toml
├── requirements.txt            # pour Streamlit Cloud
└── src/dashboard/
    ├── app.py                  # entry point — page Accueil
    ├── config.py               # settings (.env / Streamlit secrets)
    ├── data.py                 # accès BDD avec cache Streamlit
    ├── theme.py                # CSS et helpers UI
    └── pages/
        ├── 1_Qualite_de_l_air.py
        └── 2_Coach_IA.py
```

## Performance

Toutes les requêtes BDD sont cachées via `@st.cache_data` avec un TTL de
60 à 300 secondes selon la fraîcheur requise. L'engine SQLAlchemy et le
client Groq sont partagés via `@st.cache_resource`.
