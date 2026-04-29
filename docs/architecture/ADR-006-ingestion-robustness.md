# ADR 006 — Robustesse de l'ingestion AQICN et compatibilité Supabase pooler

**Statut :** Accepté
**Date :** 2026-04
**Auteur :** Colin

## Contexte

Après le merge de `feat/aqicn-client`, deux bugs ont été identifiés en
production :

1. **IDs de stations AQICN incorrects** : sur 4 stations configurées, seule
   1 était effectivement en Île-de-France. Les autres pointaient vers
   Londres et Ziyang (Chine). Résultat : pollution des analyses santé
   parisiennes par des mesures non pertinentes géographiquement.

2. **Erreur `DuplicatePreparedStatement`** : le cron de production échouait
   intermittemment avec :
   ```
   psycopg.errors.DuplicatePreparedStatement: prepared statement "_pg3_0"
   already exists
   ```
   Cause : le pooler Supabase (PgBouncer en mode `transaction`) ne supporte
   pas les prepared statements nommés que psycopg 3 crée automatiquement.

## Décisions

### Décision 1 — Vérification systématique des coordonnées AQICN

Ajouter une **garde côté CLI** qui rejette toute station AQICN dont les
coordonnées GPS ne sont pas dans la bounding box IDF (48.0-50.0°N,
1.5-3.5°E). Cette garde s'applique APRÈS la requête API : on télécharge
les données puis on vérifie avant d'insérer en base.

**Pourquoi cette approche défensive ?**

- Les IDs AQICN n'ont pas de sémantique géographique (`@5722` peut être à
  Paris ou n'importe où).
- Si quelqu'un (toi inclus, dans 6 mois) ajoute une station par erreur,
  la garde évite la pollution des données.
- Le coût est minime (1 comparaison par mesure).

### Décision 2 — Désactivation des prepared statements psycopg

Passer `prepare_threshold=None` à toutes les connexions psycopg via les
`connect_args` de SQLAlchemy. Cela désactive complètement la création de
prepared statements nommés.

**Pourquoi pas une autre approche ?**

- **Migrer vers le Direct Connection Supabase** : possible mais perd les
  avantages du pooling (max 50 connexions vs ~10000).
- **Utiliser le pooler en mode `session`** : Supabase ne propose plus ce
  mode dans son free tier.
- **Utiliser un pool d'app type SQLAlchemy** : on a déjà `NullPool` et
  c'est volontaire (le pooling est délégué à PgBouncer).

Le coût performance de désactiver les prepared statements est négligeable
(~50µs supplémentaires par requête). Acceptable pour notre volume
(~1500 inserts par run, toutes les 30 minutes).

### Décision 3 — Script de découverte des stations

Plutôt que de hardcoder à nouveau des IDs au pif, on fournit un **script
utilitaire** `scripts/discover_aqicn_stations.py` qui :

1. Interroge l'API AQICN avec une bounding box IDF
2. Filtre les stations qui retournent effectivement des données fraîches
3. Affiche un tableau avec ID, nom, coordonnées, AQI et source

L'utilisateur peut lancer `python -m ingestion.scripts.discover_aqicn_stations`
pour récupérer une liste à jour quand il veut ajouter ou ajuster les
stations couvertes.

### Décision 4 — Nettoyage des données passées

Une migration SQL `005_cleanup_parasitic_air_measurements.sql` supprime les
mesures hors IDF déjà ingérées (Londres, Ziyang, etc.). Conservée comme
trace dans le repo plutôt qu'exécutée silencieusement.

## Conséquences

### Positives

- **Fiabilité** : le cron AQICN ne plantera plus sur le bug PgBouncer
- **Pertinence** : les analyses santé portent uniquement sur des données IDF
- **Reproductibilité** : le script de découverte permet d'ajouter facilement
  des stations sans connaissance préalable des IDs AQICN
- **Lisibilité** : la garde géographique documente l'intention dans le code
  ("on n'ingère que des données IDF")

### Négatives

- **Perte de l'historique parasite** : les 3-4 mesures de Londres et Ziyang
  sont supprimées. Acceptable car non pertinentes.
- **Slight perf overhead** : ~50µs par requête sans prepared statements.
  Négligeable à notre échelle.

## Leçons apprises

1. **Vérifier les coordonnées avant d'utiliser un ID externe**. Les IDs
   numériques opaques (AQICN, GTFS, etc.) doivent être validés contre
   leur contexte sémantique.
2. **Connaître les limites du pooler de production**. PgBouncer transaction
   mode et prepared statements ne font pas bon ménage. C'est documenté chez
   Supabase mais facile à manquer.
3. **Préférer les outils de découverte aux constantes hardcodées**. Un
   script qui découvre dynamiquement les ressources est plus robuste qu'une
   liste figée.
