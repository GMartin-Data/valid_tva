#!/usr/bin/env python3
"""One-shot funnel measurement: the structural module against all 10 000 rows.

Produces the J1 headline figures: verdict distribution by motive, duplicate
excess among candidates, and the resulting count of VIES calls avoided
(numbers recorded in docs/journal.md and docs/architecture.md).

Run: uv run python exploration/03_funnel.py
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from valid_tva.structural import assess

CSV_PATH = Path(__file__).parent.parent / "data" / "numeros_tva.csv"


def main() -> None:
    """Assess every row, print the reduction funnel step by step."""
    with open(CSV_PATH, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    motives: Counter[str] = Counter()
    candidates: list[str] = []
    rebuilt_candidates = 0
    for row in rows:
        result = assess(row["numero_tva"], row["pays_declare"])
        if result.candidate:
            candidates.append(result.normalized or "")
            rebuilt_candidates += result.prefix_added
        else:
            motives[str(result.motive)] += 1

    total = len(rows)
    rejected = sum(motives.values())
    distinct = set(candidates)
    duplicate_excess = len(candidates) - len(distinct)

    print(f"total rows: {total}")
    print("\n--- structural rejections by motive ---")
    for motive, count in motives.most_common():
        print(f"  {motive}: {count}")
    print(f"  TOTAL rejected: {rejected}")

    print("\n--- candidates ---")
    print(
        f"  candidate rows: {len(candidates)} (of which {rebuilt_candidates} "
        "with rebuilt prefix)"
    )
    print(f"  distinct canonical numbers: {len(distinct)}")
    print(f"  duplicate excess rows: {duplicate_excess}")

    print("\n--- funnel summary ---")
    print(f"  naive approach:        {total} VIES calls")
    print(f"  after structural pass: {len(candidates)} rows")
    print(f"  after deduplication:   {len(distinct)} VIES calls")
    saved = total - len(distinct)
    print(f"  calls avoided: {saved} ({saved / total:.1%})")


if __name__ == "__main__":
    main()
