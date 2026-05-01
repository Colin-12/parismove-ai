# ParisMove AI — Dashboard

Dashboard Streamlit pour visualiser les données collectées par le pipeline
ParisMove AI : qualité de l'air, météo, trafic transports en commun, score
santé de trajets et coach conversationnel.

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
- 🌫️ **Qualité de l'air** : carte des stations + tendances 48h

À venir (PR 2-3) :
- 🚇 Trafic transports
- 🌿 Score santé de trajets
- 🤖 Coach IA (chat)

## Déploiement sur Streamlit Cloud

1. Inscription sur [https://streamlit.io/cloud](https://streamlit.io/cloud) avec GitHub
2. **New app** → choisir le repo `parismove-ai`
3. Branche : `develop` (ou `main` pour la prod)
4. Main file path : `services/dashboard/src/dashboard/app.py`
5. **Advanced settings → Secrets** :
   ```toml
   DATABASE_URL = "postgresql+psycopg://..."
   GROQ_API_KEY = "gsk_..."
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
        └── 1_Qualite_de_l_air.py
```

## Performance

Toutes les requêtes BDD sont cachées via `@st.cache_data` avec un TTL de
60 à 300 secondes selon la fraîcheur requise. L'engine SQLAlchemy est
partagé via `@st.cache_resource`.
