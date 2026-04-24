"""Accès à la base de données PostgreSQL (Supabase).

Ce module expose une fabrique d'engine SQLAlchemy configurée pour fonctionner
avec psycopg 3 et le Transaction Pooler de Supabase.

Le module est dans `shared` pour être réutilisable par tous les services
(ingestion écrit, api lit, coach lit).
"""
from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.pool import NullPool


def create_database_engine(database_url: str, *, echo: bool = False) -> Engine:
    """Crée un engine SQLAlchemy configuré pour Supabase.

    Args:
        database_url: URL de connexion PostgreSQL.
            Doit commencer par `postgresql+psycopg://` pour utiliser psycopg 3.
        echo: Si True, logge toutes les requêtes SQL (utile en debug).

    Returns:
        Engine SQLAlchemy. Utilise NullPool : chaque connexion est ouverte
        puis fermée immédiatement après usage, ce qui convient aux jobs cron
        courts (GitHub Actions) et au Transaction Pooler de Supabase qui
        gère lui-même le pooling côté serveur.
    """
    if not database_url.startswith("postgresql+psycopg://"):
        raise ValueError(
            "database_url doit commencer par 'postgresql+psycopg://' "
            "pour utiliser psycopg 3. Reçu : "
            f"{database_url.split('://')[0]}://..."
        )

    return create_engine(
        database_url,
        echo=echo,
        poolclass=NullPool,
        # Timeout de connexion pour ne pas bloquer la CI indéfiniment
        connect_args={"connect_timeout": 10},
    )
