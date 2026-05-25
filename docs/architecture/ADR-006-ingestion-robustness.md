# ADR-006 — Robustesse de l'ingestion AQICN

## Statut
Accepté — avril 2026

## Contexte
Deux bugs identifiés en production après le premier déploiement :

1. **Stations hors IDF** : 3 des 4 stations AQICN configurées pointaient
   vers Londres et Ziyang (Chine) — les IDs AQICN n'ont pas de sémantique
   géographique.
2. **`DuplicatePreparedStatement`** : le cron échouait intermittemment car
   psycopg 3 crée des prepared statements nommés incompatibles avec
   PgBouncer en mode transaction.

## Décision
Trois correctifs appliqués :

1. **Garde géographique** : rejet de toute station dont les coordonnées
   ne sont pas dans la bounding box IDF (48.0–50.0°N, 1.5–3.5°E), vérifié
   après la requête API, avant l'insertion en base.
2. **`prepare_threshold=None`** sur toutes les connexions psycopg via
   SQLAlchemy — désactive les prepared statements nommés (voir ADR-002).
3. **Script de découverte** `scripts/discover_aqicn_stations.py` pour
   identifier les stations IDF actives sans hardcoder des IDs au hasard.

## Conséquences
- ✅ Le cron ne plante plus sur le bug PgBouncer
- ✅ Toutes les mesures ingérées sont géographiquement pertinentes pour l'IDF
- ✅ Ajout de nouvelles stations reproductible via le script de découverte
- ⚠️ ~50µs de surcoût par requête sans prepared statements — négligeable
