"""Idempotent loader: CSV referential -> PostgreSQL with structural assessment.

Contract (brief + note 05):
- one command loads the 10 000 rows with their structural verdict and motive;
- reloading never duplicates rows (UPSERT on the CSV id);
- reloading never destroys acquired VIES verdicts (INSERT ... ON CONFLICT
  DO NOTHING on vat_numbers): overwrite the recomputable, protect the
  perishable.

Run: uv run python -m valid_tva.load [--csv data/numeros_tva.csv]
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import LiteralString, cast

import psycopg

from valid_tva.db import connect
from valid_tva.structural import assess

SCHEMA_PATH = Path(__file__).parent.parent.parent / "sql" / "schema.sql"
DEFAULT_CSV = Path("data") / "numeros_tva.csv"

UPSERT_ROW = """
INSERT INTO referential_rows
    (id, raison_sociale, pays_declare, numero_tva_raw, date_saisie,
     source_saisie, normalized, country, prefix_added,
     structural_candidate, structural_motive, vat_number)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (id) DO UPDATE SET
    raison_sociale = EXCLUDED.raison_sociale,
    pays_declare = EXCLUDED.pays_declare,
    numero_tva_raw = EXCLUDED.numero_tva_raw,
    date_saisie = EXCLUDED.date_saisie,
    source_saisie = EXCLUDED.source_saisie,
    normalized = EXCLUDED.normalized,
    country = EXCLUDED.country,
    prefix_added = EXCLUDED.prefix_added,
    structural_candidate = EXCLUDED.structural_candidate,
    structural_motive = EXCLUDED.structural_motive,
    vat_number = EXCLUDED.vat_number
"""

INSERT_NUMBER = """
INSERT INTO vat_numbers (vat_number, country, national)
VALUES (%s, %s, %s)
ON CONFLICT (vat_number) DO NOTHING
"""


@dataclass
class LoadSummary:
    """Aggregated outcome of one load, printed for the operator."""

    total_rows: int = 0
    candidates: int = 0
    distinct_numbers: int = 0
    motives: Counter[str] = field(default_factory=Counter)


def apply_schema(conn: psycopg.Connection) -> None:
    """Apply sql/schema.sql (idempotent DDL) on the given connection."""
    # psycopg types `execute` as LiteralString to block injection-prone
    # dynamic SQL; this cast asserts the file is trusted, repo-versioned DDL.
    conn.execute(cast(LiteralString, SCHEMA_PATH.read_text(encoding="utf-8")))
    conn.commit()


def load_csv(conn: psycopg.Connection, csv_path: Path) -> LoadSummary:
    """Assess and upsert every CSV row; feed vat_numbers without overwriting.

    vat_numbers is inserted first (FK target) with ON CONFLICT DO NOTHING,
    so an acquired VIES verdict survives every reload; referential_rows is
    fully upserted on the CSV id (deduced columns are recomputable).

    Returns:
        A LoadSummary with row counts, candidate count, distinct canonical
        numbers present in the database, and rejections by motive.
    """
    summary = LoadSummary()
    numbers: dict[str, tuple[str, str]] = {}
    rows: list[tuple] = []
    with open(csv_path, encoding="utf-8") as fh:
        for record in csv.DictReader(fh):
            result = assess(record["numero_tva"], record["pays_declare"])
            summary.total_rows += 1
            if result.candidate:
                summary.candidates += 1
                assert result.normalized is not None and result.country is not None
                numbers[result.normalized] = (
                    result.country,
                    result.normalized[len(result.country) :],
                )
            else:
                summary.motives[str(result.motive)] += 1
            rows.append(
                (
                    int(record["id"]),
                    record["raison_sociale"],
                    record["pays_declare"],
                    record["numero_tva"],
                    record["date_saisie"],
                    record["source_saisie"],
                    result.normalized,
                    result.country,
                    result.prefix_added,
                    result.candidate,
                    str(result.motive) if result.motive else None,
                    result.normalized if result.candidate else None,
                )
            )
    with conn.cursor() as cur:
        cur.executemany(
            INSERT_NUMBER,
            [
                (full, country, national)
                for full, (country, national) in numbers.items()
            ],
        )
        cur.executemany(UPSERT_ROW, rows)
    conn.commit()
    row = conn.execute("SELECT count(*) FROM vat_numbers").fetchone()
    summary.distinct_numbers = row[0] if row else 0
    return summary


def main(argv: list[str] | None = None) -> None:
    """CLI entry point: parse arguments, run the load, print the summary."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    args = parser.parse_args(argv)
    with connect() as conn:
        apply_schema(conn)
        summary = load_csv(conn, args.csv)
    print(f"rows loaded: {summary.total_rows}")
    print(f"candidates: {summary.candidates}")
    print(f"distinct canonical numbers: {summary.distinct_numbers}")
    print("rejections by motive:")
    for motive, count in summary.motives.most_common():
        print(f"  {motive}: {count}")


if __name__ == "__main__":
    main()
