#!/usr/bin/env python3
"""Three manual VIES probes (J2 morning, feeds decision D5 on verdict TTL).

Probes (brief, phase 2 preparation):
- a real, well-known valid number (Saint-Gobain);
- the same number with a wrong check key (structurally invalid);
- an invented number with a correct check key (passes structural checks,
  but should not exist in the registry).

For each probe, dump the FULL JSON body and the response headers — the goal
is to read everything VIES returns (dates, consultation ids, cache hints)
before deciding how long a verdict stays trustworthy (D5).

Run: uv run python exploration/04_vies_manual_probes.py
"""

import json
import time

import httpx

VIES_URL = "https://ec.europa.eu/taxation_customs/vies/rest-api/check-vat-number"
PAUSE_S = 1.0

PROBES = [
    # Saint-Gobain kept for the record: it persistently returned
    # MS_MAX_CONCURRENT_REQ (see notes/08), hence the LU fallback below.
    ("bon FR (Saint-Gobain, reel — souvent sature)", "FR", "40303265045"),
    ("bon LU (Amazon EU, reel)", "LU", "26375245"),
    ("cle fausse (41 au lieu de 40)", "FR", "41303265045"),
    ("invente (cle 09 correcte, SIREN inexistant)", "FR", "09111222333"),
]


def probe(client: httpx.Client, country: str, number: str) -> None:
    """Call VIES for one number and print status, headers and full JSON body."""
    start = time.perf_counter()
    resp = client.post(VIES_URL, json={"countryCode": country, "vatNumber": number})
    elapsed = time.perf_counter() - start
    print(f"  HTTP {resp.status_code}  ({elapsed * 1000:.0f} ms)")
    print("  headers:")
    for key, value in resp.headers.items():
        print(f"    {key}: {value}")
    try:
        body = resp.json()
    except json.JSONDecodeError:
        body = {"raw": resp.text[:500]}
    print("  body:")
    print(json.dumps(body, indent=4, ensure_ascii=False))


def main() -> None:
    """Run the three probes sequentially with a politeness pause."""
    with httpx.Client(timeout=30) as client:
        for label, country, number in PROBES:
            print(f"\n=== {label}: {country}{number} ===")
            try:
                probe(client, country, number)
            except httpx.HTTPError as exc:
                print(f"  ERROR {type(exc).__name__}: {exc}")
            time.sleep(PAUSE_S)


if __name__ == "__main__":
    main()
