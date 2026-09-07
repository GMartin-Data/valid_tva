#!/usr/bin/env python3
"""One-shot VIES latency measurement (J1, before designing the campaign).

Goals (brief, phase 1):
- measure response time on a handful of real calls;
- extrapolate to the full 10 000-row referential (naive approach);
- bonus probes: how VIES reacts to a GB prefix (post-Brexit, feeds decision D3)
  and to a nonexistent country code (ZZ).

Run: uv run python exploration/02_vies_timing.py
"""

import csv
import json
import re
import statistics
import time
from pathlib import Path

import httpx

CSV_PATH = Path(__file__).parent.parent / "data" / "numeros_tva.csv"
VIES_URL = "https://ec.europa.eu/taxation_customs/vies/rest-api/check-vat-number"
EU_COUNTRIES = {"FR", "DK", "BE", "LU", "SE", "PT", "NL", "IT", "PL", "FI"}
TIMING_CALLS = 10
PAUSE_S = 0.5


def normalize(value: str) -> str:
    """Uppercase and drop every non-alphanumeric character."""
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def pick_samples() -> list[tuple[str, str]]:
    """One clean-looking number per EU country found in the referential."""
    samples: dict[str, str] = {}
    with open(CSV_PATH, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            number = normalize(row["numero_tva"])
            country = number[:2]
            if country in EU_COUNTRIES and country not in samples:
                samples[country] = number[2:]
            if len(samples) == len(EU_COUNTRIES):
                break
    return list(samples.items())


def check(client: httpx.Client, country: str, number: str) -> tuple[float, int, dict]:
    """Call VIES for one number; return (elapsed seconds, HTTP status, JSON body)."""
    start = time.perf_counter()
    resp = client.post(VIES_URL, json={"countryCode": country, "vatNumber": number})
    elapsed = time.perf_counter() - start
    try:
        body = resp.json()
    except json.JSONDecodeError:
        body = {"raw": resp.text[:200]}
    return elapsed, resp.status_code, body


def main() -> None:
    """Time sequential VIES calls, probe out-of-scope countries, extrapolate."""
    samples = pick_samples()[:TIMING_CALLS]
    timings: list[float] = []

    with httpx.Client(timeout=30) as client:
        print(f"--- timing: {len(samples)} sequential calls, {PAUSE_S}s pause ---")
        for country, number in samples:
            try:
                elapsed, status, body = check(client, country, number)
            except httpx.HTTPError as exc:
                print(f"  {country}{number}: ERROR {type(exc).__name__}: {exc}")
                continue
            timings.append(elapsed)
            print(
                f"  {country}{number}: {elapsed * 1000:6.0f} ms  HTTP {status}"
                f"  valid={body.get('valid')}  name={str(body.get('name'))[:30]!r}"
            )
            time.sleep(PAUSE_S)

        print("\n--- probes (full JSON) ---")
        for country, number in [("GB", "983761159"), ("ZZ", "23140153")]:
            try:
                elapsed, status, body = check(client, country, number)
                print(f"  {country}{number} (HTTP {status}, {elapsed * 1000:.0f} ms):")
                print(f"    {json.dumps(body, ensure_ascii=False)}")
            except httpx.HTTPError as exc:
                print(f"  {country}{number}: ERROR {type(exc).__name__}: {exc}")

    if not timings:
        print("\nNo successful call — no extrapolation possible.")
        return

    median = statistics.median(timings)
    mean = statistics.fmean(timings)
    print(f"\n--- stats over {len(timings)} calls ---")
    print(
        f"  min {min(timings):.2f}s  median {median:.2f}s  mean {mean:.2f}s  max {max(timings):.2f}s"
    )

    print("\n--- naive extrapolation: 10 000 sequential calls ---")
    for label, per_call in [
        ("median latency alone", median),
        (f"median + {PAUSE_S}s politeness pause", median + PAUSE_S),
    ]:
        total_s = 10_000 * per_call
        print(f"  {label}: {total_s / 3600:.1f} h ({total_s / 60:.0f} min)")


if __name__ == "__main__":
    main()
