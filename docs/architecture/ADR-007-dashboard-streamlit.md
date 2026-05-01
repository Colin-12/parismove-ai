# ADR 007 — Dashboard Streamlit

**Statut :** Accepté
**Date :** 2026-04
**Auteur :** Colin

## Contexte

Le projet ParisMove AI a accumulé 3 services data (ingestion, healthscore,
coach) et collecte 3 sources temps-réel via cron. Pour rendre toutes ces
données exploitables par un utilisateur final (et démonstrables en
soutenance), il faut une **interface visuelle**.

Les options principales étaient :

1. **Streamlit** : framework Python orienté data science, déploiement gratuit
   via Streamlit Cloud.
2. **FastAPI + React** : API REST + frontend SPA, plus pro mais ~10x plus
   de boulot.
3. **Dash (Plotly)** : équivalent Streamlit côté data, légèrement moins
   intuitif pour la mise en page.
4. **Notebook Jupyter** : très data-scientist, mais pas une vraie UI partageable.

## Décision

Adopter **Streamlit** pour le dashboard, avec :

- **Service séparé** `services/dashboard` (5e service du monorepo)
- **Multi-pages natif** via le dossier `pages/`
- **Déploiement continu** sur Streamlit Cloud à chaque push develop
- **Carte interactive Folium** pour la dimension géospatiale
- **Plotly** pour les graphiques (line, area, bar)
- **Cache Streamlit** (`cache_data` et `cache_resource`) pour la performance

## Justifications

### Pourquoi Streamlit plutôt que FastAPI + React ?

- **Vélocité** : un dashboard 4 pages prêt en 6-8h vs 3-4 jours
- **Cible** : projet étudiant, pas un produit en prod scaleable
- **Stack cohérente** : tout en Python, pas de contexte JS/TS à gérer
- **Streamlit Cloud gratuit** : URL publique sans hébergement à payer
- **Iteration rapide** : `runOnSave = true`, le dev sent natif

L'inconvénient principal est la moins grande customisation UX, mais c'est
acceptable pour notre besoin.

### Pourquoi un service séparé ?

Cohérent avec l'architecture microservices déjà en place. Le dashboard
peut être déployé/redéployé indépendamment de l'ingestion ou du coach.

C'est aussi mieux pour la séparation des concerns : la BDD est lue par
le dashboard, écrite uniquement par l'ingestion. Pas de risque de
contention ou d'interférence.

### Pourquoi multipage ?

4 pages (Accueil, Air, Trafic, Score) plus le chat IA = un volume de
contenu trop important pour une page unique. Le multipage Streamlit a
une excellente UX (sidebar de navigation native).

### Pourquoi Folium et pas un autre lib de carte ?

- **Folium est mature** : wrapper Python autour de Leaflet.js
- **Intégration Streamlit native** via `streamlit-folium`
- **Pas de clé API requise** (à la différence de Mapbox)
- **Backend OpenStreetMap / CartoDB** gratuit et performant

### Stratégie de cache

Le dashboard interroge la BDD à chaque interaction utilisateur. Sans
cache, ça poutre la BDD Supabase et ralentit l'UX.

Notre stratégie :

- `@st.cache_resource` pour l'**engine SQLAlchemy** (1 instance par session)
- `@st.cache_data(ttl=60)` pour les **mesures fraîches** (vue d'ensemble)
- `@st.cache_data(ttl=300)` pour les **historiques** (5 min de cache OK)

## Conséquences

### Positives

- **URL publique** déployée en continu pour partager aux recruteurs
- **Architecture cohérente** avec le reste du projet (microservice)
- **Réutilisation maximale** des services existants (healthscore, coach)
- **UX progressive** : 3 PR successives pour livrer en itératif

### Négatives

- **Limitations Streamlit** sur la customisation UX très poussée
- **Monorepo + Streamlit Cloud** : nécessite un `requirements.txt` racine
  avec des `-e` relatifs (configuration spécifique documentée dans le
  README)
- **Coût performance** des reruns Streamlit (mitigé par le cache)

## Découpe en PRs

- **PR 1 (cette PR)** : fondations + Accueil + Qualité de l'air
- **PR 2** : Trafic transports + Score santé interactif
- **PR 3** : Coach IA embedded (chat)

## Structure

```
services/dashboard/
├── pyproject.toml
├── requirements.txt          # pour Streamlit Cloud
├── README.md
└── src/dashboard/
    ├── app.py                # entry point — page Accueil
    ├── config.py             # settings (.env / Streamlit secrets)
    ├── data.py               # accès BDD avec cache Streamlit
    ├── theme.py              # CSS et helpers UI (header, kpi_card, badge)
    ├── py.typed
    └── pages/
        └── 1_Qualite_de_l_air.py
```
