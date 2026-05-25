# ADR-007 — Dashboard Streamlit

## Statut
Accepté — avril 2026

## Contexte
Le projet dispose de 3 services data (ingestion, healthscore, coach) et
collecte 3 sources temps-réel. Il faut une interface visuelle déployable
gratuitement, démontrable en soutenance, construite rapidement.

## Décision
**Streamlit** comme framework dashboard, déployé sur Streamlit Community
Cloud (URL publique, redéploiement automatique à chaque push sur `develop`).

Architecture retenue :
- Service séparé `services/dashboard` (cohérent avec le reste du monorepo)
- Multi-pages natif via le dossier `pages/`
- **Folium** pour les cartes (wrapper Leaflet.js, gratuit, pas de clé API)
- **Plotly** pour les graphiques
- **Cache Streamlit** : `cache_resource` pour l'engine SQL, `cache_data(ttl=60)`
  pour les mesures fraîches, `cache_data(ttl=300)` pour les historiques

## Conséquences
- ✅ URL publique déployée en continu, partageable aux recruteurs
- ✅ Vélocité : dashboard 5 pages en quelques heures vs jours avec FastAPI+React
- ✅ Stack 100 % Python, cohérente avec le reste du projet
- ⚠️ Customisation UX limitée par rapport à un frontend React
- ⚠️ `requirements.txt` racine nécessaire pour Streamlit Cloud
  (configuration documentée dans le README)
