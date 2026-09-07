"""Integration tests for the idempotent loader (need the compose PostgreSQL).

Skipped cleanly when no server answers on the configured port. Tests run
against a throwaway database (tva_test), rebuilt at every session: the real
referential database is never touched.

The fixture CSV covers every path: candidate, noisy duplicate pair, rebuilt
prefix, disguised emptiness, unknown country, bad format, bad check digit.
"""

from __future__ import annotations

from pathlib import Path

import psycopg
import pytest

from valid_tva.db import connect, connection_string
from valid_tva.load import apply_schema, load_csv

TEST_DB = "tva_test"

FIXTURE_CSV = """\
id,raison_sociale,pays_declare,numero_tva,date_saisie,source_saisie
1,Alpha SAS,FR,FR40303265045,2024-01-01,crm
2,Bravo ApS,DK,DK 1358 5628,2024-02-01,crm
3,Bravo ApS,DK,dk13585628,2024-03-01,import_fournisseur
4,Charlie NV,BE,NU.LL,2024-04-01,saisie_manuelle
5,Delta Sp,ZZ,ZZ12345678,2024-05-01,reprise_erp
6,Echo ApS,DK,DK1234567,2024-06-01,portail_client
7,Foxtrot ApS,DK,13585629,2024-07-01,crm
"""


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


@pytest.fixture
def csv_path(tmp_path: Path) -> Path:
    """Write the 7-row fixture CSV to a temporary file."""
    path = tmp_path / "fixture.csv"
    path.write_text(FIXTURE_CSV, encoding="utf-8")
    return path


def fetch_one(conn: psycopg.Connection, query: str) -> tuple:
    """Run a query and return its single row."""
    return conn.execute(query).fetchone()


class TestSingleLoad:
    """One load: rows, verdicts, links."""

    def test_every_row_is_loaded_with_its_verdict(self, conn, csv_path) -> None:
        """7 rows in, 7 rows stored; 3 candidates; motives populated."""
        summary = load_csv(conn, csv_path)
        assert summary.total_rows == 7
        assert summary.candidates == 3  # ids 1, 2, 3
        assert fetch_one(conn, "SELECT count(*) FROM referential_rows")[0] == 7
        assert summary.motives == {
            "MISSING": 1,
            "UNKNOWN_COUNTRY": 1,
            "BAD_FORMAT": 1,
            "BAD_CHECK_DIGIT": 1,
        }

    def test_duplicates_converge_to_one_number(self, conn, csv_path) -> None:
        """The two DK graphies (ids 2, 3) point to the same vat_number row."""
        summary = load_csv(conn, csv_path)
        assert summary.distinct_numbers == 2  # FR + DK
        rows = conn.execute(
            "SELECT id, vat_number FROM referential_rows WHERE id IN (2, 3)"
        ).fetchall()
        assert [r[1] for r in rows] == ["DK13585628", "DK13585628"]

    def test_rejected_rows_have_no_number(self, conn, csv_path) -> None:
        """Rejected rows (ids 4-6) never reach the VIES stage: NULL link."""
        load_csv(conn, csv_path)
        count = fetch_one(
            conn,
            "SELECT count(*) FROM referential_rows"
            " WHERE id IN (4, 5, 6) AND vat_number IS NULL",
        )[0]
        assert count == 3

    def test_rebuilt_prefix_is_traced(self, conn, csv_path) -> None:
        """Id 7 (no prefix, bad key): prefix_added AND rejected for its key."""
        load_csv(conn, csv_path)
        row = fetch_one(
            conn,
            "SELECT prefix_added, structural_motive, normalized"
            " FROM referential_rows WHERE id = 7",
        )
        assert row == (True, "BAD_CHECK_DIGIT", "DK13585629")

    def test_raw_value_is_stored_untouched(self, conn, csv_path) -> None:
        """The received value stays exactly as received (noisy spaces kept)."""
        load_csv(conn, csv_path)
        raw = fetch_one(
            conn, "SELECT numero_tva_raw FROM referential_rows WHERE id = 2"
        )[0]
        assert raw == "DK 1358 5628"


class TestReload:
    """The two idempotence guarantees (note 05)."""

    def test_reload_never_duplicates(self, conn, csv_path) -> None:
        """Loading twice leaves exactly the same row counts."""
        load_csv(conn, csv_path)
        load_csv(conn, csv_path)
        assert fetch_one(conn, "SELECT count(*) FROM referential_rows")[0] == 7
        assert fetch_one(conn, "SELECT count(*) FROM vat_numbers")[0] == 2

    def test_reload_preserves_acquired_verdicts(self, conn, csv_path) -> None:
        """Overwrite the recomputable, protect the perishable: a VIES verdict
        acquired between two loads survives the second load."""
        load_csv(conn, csv_path)
        conn.execute(
            "UPDATE vat_numbers SET vies_status = 'valid',"
            " vies_checked_at = now(), vies_name = 'ACME'"
            " WHERE vat_number = 'DK13585628'"
        )
        conn.commit()
        load_csv(conn, csv_path)
        status, name = fetch_one(
            conn,
            "SELECT vies_status, vies_name FROM vat_numbers"
            " WHERE vat_number = 'DK13585628'",
        )
        assert (status, name) == ("valid", "ACME")


class TestMotiveDistribution:
    """The end-of-J1 testable query."""

    def test_distribution_query_matches_load(self, conn, csv_path) -> None:
        """sql/motive_distribution.sql returns the expected breakdown."""
        load_csv(conn, csv_path)
        query = (Path("sql") / "motive_distribution.sql").read_text(encoding="utf-8")
        distribution = dict(conn.execute(query).fetchall())
        assert distribution == {
            "CANDIDATE": 3,
            "MISSING": 1,
            "UNKNOWN_COUNTRY": 1,
            "BAD_FORMAT": 1,
            "BAD_CHECK_DIGIT": 1,
        }
