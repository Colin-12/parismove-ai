# ADR-002 — Driver PostgreSQL et pooling

## Statut
Accepté — avril 2026

## Contexte
Le service d'ingestion tourne dans GitHub Actions (jobs courts, créés et
détruits à chaque run) et doit se connecter au Transaction Pooler Supabase
(port 6543). Il faut choisir un driver Python et une stratégie de connexion
adaptés.

## Décision
**psycopg 3** avec SQLAlchemy et **NullPool** côté Python.

- `psycopg 3` : maintenance active, meilleures performances en batch,
  support async natif. URL SQLAlchemy : `postgresql+psycopg://`
- `NullPool` : chaque requête ouvre et ferme sa connexion. Adapté aux
  jobs cron courts — pas de pool à maintenir en mémoire, pas de fuite
  de connexion. Le pooling est délégué à PgBouncer côté Supabase.
- `prepare_threshold=None` : désactive les prepared statements nommés,
  incompatibles avec PgBouncer en mode transaction (cf. ADR-006).

## Conséquences
- ✅ Aucune fuite de connexion dans les jobs cron
- ✅ Compatible avec n'importe quel environnement (local, CI, serveur)
- ⚠️ Si on passe à un service long-running (FastAPI), il faudra activer
  un `QueuePool` côté application
