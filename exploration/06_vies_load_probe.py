#!/usr/bin/env python3
"""Hourly VIES load probe (J2 evening -> Thursday, feeds the launch window).

One cycle = one call to each witness member state (FR, BE, DK — the most
saturated ones observed in notes/08), appending one CSV line per call:
timestamp, country, outcome, latency_ms. Run hourly by cron, the resulting
series maps the real load curve and validates (or not) the Thursday-night
window for the full campaign run.

The witness numbers are fixed referential candidates already carrying a
fresh verdict: probing them touches no database state and stays comparable
from one cycle to the next.

Run: uv run python exploration/06_vies_load_probe.py
"""

import csv
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

VIES_URL = "https://ec.europa.eu/taxation_customs/vies/rest-api/check-vat-number"
CSV_PATH = (
    Path(__file__).parent.parent.parent / "brief_valid_tva" / "vies-load-probe.csv"
)
WITNESSES = [("FR", "14760307373"), ("BE", "0311256964"), ("DK", "72344081")]


def outcome_of(body: dict) -> str:
    """Collapse a VIES body onto the notes/08 taxonomy, error code included."""
    if "errorWrappers" in body:
        return body["errorWrappers"][0].get("error", "UNKNOWN_WRAPPER")
    if "valid" in body:
        return f"valid={body['valid']}"
    return "unexpected-shape"


def main() -> None:
    """Probe each witness once and append the results to the CSV series."""
    is_new = not CSV_PATH.exists()
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        if is_new:
            writer.writerow(["timestamp_utc", "country", "outcome", "latency_ms"])
        with httpx.Client(timeout=30) as client:
            for country, national in WITNESSES:
                stamp = datetime.now(UTC).isoformat(timespec="seconds")
                start = time.perf_counter()
                try:
                    resp = client.post(
                        VIES_URL,
                        json={"countryCode": country, "vatNumber": national},
                    )
                    outcome = outcome_of(resp.json())
                except httpx.HTTPError as exc:
                    outcome = f"transport:{type(exc).__name__}"
                latency_ms = round((time.perf_counter() - start) * 1000)
                writer.writerow([stamp, country, outcome, latency_ms])
                print(f"{stamp} {country}: {outcome} ({latency_ms} ms)")
                time.sleep(1)


if __name__ == "__main__":
    main()
