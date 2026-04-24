# ADR 002 — Driver PostgreSQL et pooling

**Statut :** Accepté
**Date :** 2026-04
**Auteur :** Colin

## Contexte

Le service d'ingestion doit persister les passages captés dans PostgreSQL (Supabase). Il faut choisir un driver Python et une stratégie de gestion des connexions compatibles avec :

- L'exécution dans GitHub Actions (jobs courts, créés/détruits à chaque run)
- Le Transaction Pooler de Supabase (port 6543)
- Le niveau gratuit Supabase (limite de connexions)

## Décision

Utiliser **psycopg 3** (et non psycopg2) avec SQLAlchemy, et désactiver le pooling côté Python (`NullPool`).

## Justification

### Pourquoi psycopg 3

- Support natif de `async` (utile si on veut à terme de l'ingestion concurrente)
- Meilleures performances sur les inserts en batch via `COPY`
- Maintenance active (psycopg2 est en mode maintenance seulement)
- Syntaxe d'URL : doit préfixer par `postgresql+psycopg://` pour SQLAlchemy

### Pourquoi NullPool

GitHub Actions démarre un job, exécute l'ingestion en quelques secondes, puis tue le process. Garder un pool de connexions en mémoire n'a aucun sens dans ce cycle court. De plus, le Transaction Pooler de Supabase gère déjà le pooling au niveau serveur : maintenir un autre pool côté client empile deux couches de pooling pour rien.

Avec NullPool : chaque requête ouvre une connexion, l'utilise, la ferme. Simple et adapté aux jobs batch.

## Conséquences

### Positives

- Setup minimal, pas de configuration de pool à gérer
- Pas de risque de "connection leak" dans les jobs cron
- Compatible avec n'importe quel environnement (local, CI, serveur)

### Négatives

- Latence supplémentaire à chaque connexion (ouverture TCP + auth). Pour des batches de taille modeste (quelques centaines de lignes toutes les 15 minutes), négligeable.
- Si on passait un jour à un service long-running (API FastAPI), il faudrait revoir cette décision et activer un pool (`QueuePool`).

## Alternatives rejetées

- **psycopg2** : moins performant, en fin de vie côté maintenance
- **asyncpg direct** (sans SQLAlchemy) : plus rapide mais on perd l'abstraction ORM/Core qu'on utilisera probablement dans les autres services
- **QueuePool côté Python** : inutile pour des jobs cron, source de bugs potentiels (connexions non libérées à la fin du job)
