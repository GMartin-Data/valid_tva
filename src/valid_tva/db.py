"""Database access: connection settings from the environment.

Defaults match docker-compose.yml so `docker compose up -d` works with no
further configuration.
"""

from __future__ import annotations

import os

import psycopg


def connection_string(dbname: str | None = None) -> str:
    """Build a libpq connection string from POSTGRES_* env vars.

    Args:
        dbname: override the target database (used by tests to point at a
            throwaway database instead of the real referential).
    """
    return (
        f"host={os.environ.get('POSTGRES_HOST', 'localhost')}"
        f" port={os.environ.get('POSTGRES_PORT', '5435')}"
        f" user={os.environ.get('POSTGRES_USER', 'meridian')}"
        f" password={os.environ.get('POSTGRES_PASSWORD', 'meridian')}"
        f" dbname={dbname or os.environ.get('POSTGRES_DB', 'tva')}"
    )


def connect(dbname: str | None = None) -> psycopg.Connection:
    """Open a psycopg connection to the referential database."""
    return psycopg.connect(connection_string(dbname))
