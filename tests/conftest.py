"""Shared fixtures for the integration tests (throwaway tva_test database).

Skipped cleanly when no PostgreSQL answers on the configured port. The
throwaway database is rebuilt once per session; each test gets a fresh
connection with the schema applied and both tables emptied — the real
referential database is never touched.
"""

from __future__ import annotations

import psycopg
import pytest

from valid_tva.db import connect, connection_string
from valid_tva.load import apply_schema

TEST_DB = "tva_test"


@pytest.fixture(scope="session")
def test_db() -> str:
    """Rebuild a throwaway database, or skip when PostgreSQL is unreachable."""
    try:
        admin = psycopg.connect(connection_string("postgres"), autocommit=True)
    except psycopg.OperationalError:
        pytest.skip("PostgreSQL not reachable (run: docker compose up -d)")
    admin.execute(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")
    admin.execute(f"CREATE DATABASE {TEST_DB}")
    admin.close()
    return TEST_DB


@pytest.fixture
def conn(test_db: str) -> psycopg.Connection:
    """Fresh connection per test, schema applied, tables emptied."""
    with connect(test_db) as connection:
        apply_schema(connection)
        connection.execute("TRUNCATE referential_rows, vat_numbers")
        connection.commit()
        yield connection


def seed(
    conn: psycopg.Connection,
    number: str,
    status: str | None = None,
    checked_days_ago: int | None = None,
    name: str | None = None,
    address: str | None = None,
) -> None:
    """Insert one canonical number, optionally with an observed VIES verdict."""
    conn.execute(
        "INSERT INTO vat_numbers (vat_number, country, national,"
        " vies_status, vies_checked_at, vies_name, vies_address)"
        " VALUES (%s, %s, %s, %s,"
        " CASE WHEN %s::int IS NULL THEN NULL"
        "      ELSE now() - make_interval(days => %s) END, %s, %s)",
        (
            number,
            number[:2],
            number[2:],
            status,
            checked_days_ago,
            checked_days_ago,
            name,
            address,
        ),
    )
    conn.commit()
