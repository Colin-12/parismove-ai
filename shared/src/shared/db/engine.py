"""Création de l'engine SQLAlchemy pour PostgreSQL.

ParisMove AI utilise Supabase qui expose PostgreSQL via un Transaction Pooler
(PgBouncer en mode `transaction`). Ce mode a une limitation importante :
**il ne supporte pas les prepared statements nommés** côté client.

Avec psycopg 3 (notre driver), les prepared statements sont créés
automatiquement après quelques exécutions de la même requête (par défaut
`prepare_threshold=5`). Quand le pooler distribue les exécutions sur
différentes connexions backend, ces prepared statements génèrent l'erreur :

    psycopg.errors.DuplicatePreparedStatement:
    prepared statement "_pg3_0" already exists

La solution : passer `prepare_threshold=None` à psycopg, ce qui désactive
totalement la création de prepared statements. Léger surcoût en perf
(quelques microsecondes par requête), mais c'est le pattern recommandé
par Supabase pour leur pooler.

Réf : https://www.psycopg.org/psycopg3/docs/api/connections.html#psycopg.Connection.prepare_threshold
Réf : https://supabase.com/docs/guides/database/connecting-to-postgres#pooler-mode
"""
from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.pool import NullPool


def create_database_engine(database_url: str) -> Engine:
    """Crée un engine SQLAlchemy adapté à Supabase Transaction Pooler.

    Args:
        database_url: URL au format `postgresql+psycopg://...`

    Returns:
        Un Engine configuré pour fonctionner avec PgBouncer transaction mode.
    """
    return create_engine(
        database_url,
        # NullPool : pas de pooling côté SQLAlchemy, on délègue au pooler Supabase
        poolclass=NullPool,
        # Désactivation des prepared statements (incompatibles avec le pooler)
        connect_args={
            "prepare_threshold": None,
        },
        # Ping avant chaque utilisation pour détecter les connexions mortes
        pool_pre_ping=True,
    )
