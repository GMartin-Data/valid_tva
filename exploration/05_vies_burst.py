#!/usr/bin/env python3
"""Burst of sequential VIES calls on real candidates (J2, feeds the campaign).

Goal: a few dozen calls in a row on structurally-valid numbers from the
referential, observing the non-passing cases with the response taxonomy from
notes/08: valid true / valid false / wrapped error (code) / transport error.
Prints per-outcome counts, latency stats, and full detail of every anomaly.

Run: uv run python exploration/05_vies_burst.py
"""

from __future__ import annotations

import csv
import json
import statistics
import time
from collections import Counter
from pathlib import Path

import httpx

from valid_tva.structural import assess

CSV_PATH = Path(__file__).parent.parent / "data" / "numeros_tva.csv"
VIES_URL = "https://ec.europa.eu/taxation_customs/vies/rest-api/check-vat-number"
PER_COUNTRY = 4
PAUSE_S = 0.5


def pick_sample() -> list[str]:
    """Up to PER_COUNTRY distinct canonical candidates per country, CSV order."""
    per_country: Counter[str] = Counter()
    sample: list[str] = []
    seen: set[str] = set()
    with open(CSV_PATH, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            result = assess(row["numero_tva"], row["pays_declare"])
            number = result.normalized or ""
            if not result.candidate or number in seen:
                continue
            country = number[:2]
            if per_country[country] >= PER_COUNTRY:
                continue
            seen.add(number)
            per_country[country] += 1
            sample.append(number)
    return sample


def classify(body: dict) -> str:
    """Map a VIES JSON body onto the notes/08 taxonomy."""
    if "errorWrappers" in body:
        return f"error:{body['errorWrappers'][0].get('error', '?')}"
    if "valid" in body:
        return f"valid:{body['valid']}"
    return "unexpected-shape"


def main() -> None:
    """Call VIES sequentially on the sample and summarize outcomes."""
    sample = pick_sample()
    print(f"--- burst: {len(sample)} sequential calls, {PAUSE_S}s pause ---")

    outcomes: Counter[str] = Counter()
    timings: list[float] = []
    anomalies: list[tuple[str, str, dict]] = []

    with httpx.Client(timeout=30) as client:
        for number in sample:
            country, digits = number[:2], number[2:]
            start = time.perf_counter()
            try:
                resp = client.post(
                    VIES_URL, json={"countryCode": country, "vatNumber": digits}
                )
                body = resp.json()
            except (httpx.HTTPError, json.JSONDecodeError) as exc:
                outcome = f"transport:{type(exc).__name__}"
                outcomes[outcome] += 1
                anomalies.append((number, outcome, {"detail": str(exc)[:200]}))
                print(f"  {number}: {outcome}")
                time.sleep(PAUSE_S)
                continue
            elapsed = time.perf_counter() - start
            timings.append(elapsed)
            outcome = classify(body)
            outcomes[outcome] += 1
            if not outcome.startswith("valid:"):
                anomalies.append((number, outcome, body))
            name = str(body.get("name", ""))[:30]
            print(f"  {number}: {elapsed * 1000:6.0f} ms  {outcome:<12} {name!r}")
            time.sleep(PAUSE_S)

    print("\n--- outcomes ---")
    for outcome, count in outcomes.most_common():
        print(f"  {outcome}: {count}")

    if timings:
        print("\n--- latency over successful HTTP exchanges ---")
        print(
            f"  min {min(timings):.2f}s  median {statistics.median(timings):.2f}s"
            f"  mean {statistics.fmean(timings):.2f}s  max {max(timings):.2f}s"
        )

    if anomalies:
        print("\n--- anomalies (full bodies) ---")
        for number, outcome, body in anomalies:
            print(f"  {number} [{outcome}]:")
            print(json.dumps(body, indent=4, ensure_ascii=False))


if __name__ == "__main__":
    main()
