#!/usr/bin/env python3
"""One-shot exploration of the raw VAT referential (J1, before any production code).

Findings are recorded in docs/journal.md; this script is kept for traceability
and is NOT part of the production pipeline.

Run: uv run python exploration/01_explore_csv.py
"""

import csv
import re
from collections import Counter
from pathlib import Path

PATH = Path(__file__).parent.parent / "data" / "numeros_tva.csv"

EMPTY_FORMS = {"N/A", "NA", "NULL", "NONE", "-", "?"}


def is_emptyish(value: str) -> bool:
    """True for every observed form of 'no value', incl. disguised ones (NU.LL)."""
    stripped = value.strip().upper()
    return stripped == "" or stripped in EMPTY_FORMS or normalize(value) in EMPTY_FORMS


def normalize(value: str) -> str:
    """Uppercase and drop every non-alphanumeric character."""
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def main() -> None:
    """Print counts for countries, empties, noise, prefixes, duplicates, sources."""
    with open(PATH, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    print(f"rows: {len(rows)}, columns: {list(rows[0].keys())}")
    print(f"distinct ids: {len({r['id'] for r in rows})}")

    print(f"\n--- pays_declare ({len({r['pays_declare'] for r in rows})} distinct) ---")
    for country, n in Counter(r["pays_declare"] for r in rows).most_common():
        print(f"  {country!r}: {n}")

    empties = Counter(repr(r["numero_tva"]) for r in rows if is_emptyish(r["numero_tva"]))
    print(f"\n--- empty-ish numero_tva: {sum(empties.values())} rows ---")
    for form, n in empties.most_common():
        print(f"  {form}: {n}")

    noise = Counter()
    for r in rows:
        if not is_emptyish(r["numero_tva"]):
            for char in set(re.findall(r"[^A-Za-z0-9]", r["numero_tva"])):
                noise[char] += 1
    n_noisy = sum(
        1
        for r in rows
        if not is_emptyish(r["numero_tva"]) and re.search(r"[^A-Za-z0-9]", r["numero_tva"])
    )
    n_lower = sum(
        1
        for r in rows
        if not is_emptyish(r["numero_tva"]) and any(c.islower() for c in r["numero_tva"])
    )
    print(f"\n--- noise: {n_noisy} rows with non-alphanumeric chars, {n_lower} with lowercase ---")
    for char, n in noise.most_common():
        print(f"  {char!r}: {n} rows")

    usable = [r for r in rows if not is_emptyish(r["numero_tva"])]
    no_prefix = [r for r in usable if not re.match(r"^[A-Z]{2}", normalize(r["numero_tva"]))]
    mismatch = [
        r
        for r in usable
        if re.match(r"^[A-Z]{2}", normalize(r["numero_tva"]))
        and normalize(r["numero_tva"])[:2] != r["pays_declare"].strip().upper()
    ]
    print(f"\n--- prefix: {len(no_prefix)} rows without country prefix, "
          f"{len(mismatch)} prefix/country mismatches ---")
    print(f"  no-prefix by country: {Counter(r['pays_declare'] for r in no_prefix)}")

    raw_counts = Counter(r["numero_tva"] for r in usable)
    norm_counts = Counter(normalize(r["numero_tva"]) for r in usable)
    raw_excess = sum(n - 1 for n in raw_counts.values() if n > 1)
    norm_excess = sum(n - 1 for n in norm_counts.values() if n > 1)
    print(f"\n--- duplicates: raw excess rows {raw_excess}, normalized excess rows {norm_excess} ---")

    print(f"\n--- source_saisie: {dict(Counter(r['source_saisie'] for r in rows))} ---")
    dates = sorted(r["date_saisie"] for r in rows if r["date_saisie"].strip())
    print(f"--- date_saisie: {dates[0]} -> {dates[-1]}, empty: {len(rows) - len(dates)} ---")


if __name__ == "__main__":
    main()
