#!/usr/bin/env python3
"""Pick the launch window for the full run from the load-probe series.

Reads the CSV accumulated by 06_vies_load_probe.py and aggregates outcomes
by local hour of day (Europe/Paris — the launch decision is a local-time
one) and by country. A call is "saturated" when VIES did not return a
normal valid=... body (MS_MAX_CONCURRENT_REQ, MS_UNAVAILABLE, ...).

Criterion, fixed BEFORE looking at the data (progress.md step 1): the
contiguous window of >= 3 hours with the minimal saturation rate wins;
ties are broken by the median latency of successful calls. All 24
circular 3-hour windows are ranked; a window is skipped if one of its
hours has no measurement. Degraded mode (no discriminating window) is a
human call: launch at 22:00 local anyway.

Run: uv run python exploration/07_launch_window.py
"""

import csv
import statistics
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

CSV_PATH = (
    Path(__file__).parent.parent.parent / "brief_valid_tva" / "vies-load-probe.csv"
)
PARIS = ZoneInfo("Europe/Paris")
WINDOW_HOURS = 3


def load_rows() -> list[tuple[int, str, bool, int]]:
    """Parse the probe CSV into (local_hour, country, ok, latency_ms) rows."""
    rows = []
    with open(CSV_PATH, newline="", encoding="utf-8") as fh:
        for rec in csv.DictReader(fh):
            stamp = datetime.fromisoformat(rec["timestamp_utc"]).astimezone(PARIS)
            ok = rec["outcome"].startswith("valid=")
            rows.append((stamp.hour, rec["country"], ok, int(rec["latency_ms"])))
    return rows


def hourly_table(rows: list[tuple[int, str, bool, int]]) -> None:
    """Print the hour x country saturation table with per-hour medians."""
    countries = sorted({country for _, country, _, _ in rows})
    print(f"hour  {'  '.join(f'{c}:sat' for c in countries)}   all:sat  n   med_ok_ms")
    for hour in range(24):
        cells = []
        for country in countries:
            calls = [ok for h, c, ok, _ in rows if h == hour and c == country]
            cells.append(f"{sat_rate(calls):>6}" if calls else "     -")
        calls = [ok for h, _, ok, _ in rows if h == hour]
        ok_lat = [ms for h, _, ok, ms in rows if h == hour and ok]
        med = f"{statistics.median(ok_lat):.0f}" if ok_lat else "-"
        print(
            f"{hour:02d}h   {'  '.join(cells)}   {sat_rate(calls):>7}  "
            f"{len(calls):<3} {med:>6}"
        )


def sat_rate(calls: list[bool]) -> str:
    """Format the saturation rate of a list of ok-flags as a percentage."""
    return f"{100 * (1 - sum(calls) / len(calls)):.0f}%"


def rank_windows(rows: list[tuple[int, str, bool, int]]) -> list[dict]:
    """Rank every circular 3-hour window by (saturation rate, median ok latency)."""
    windows = []
    for start in range(24):
        hours = [(start + offset) % 24 for offset in range(WINDOW_HOURS)]
        calls = [(ok, ms) for h, _, ok, ms in rows if h in hours]
        if any(not any(h == hour for h, _, _, _ in rows) for hour in hours):
            continue  # an hour without data cannot support a verdict
        ok_lat = [ms for ok, ms in calls if ok]
        windows.append(
            {
                "window": f"{hours[0]:02d}h-{(hours[-1] + 1) % 24:02d}h",
                "saturation": round(1 - len(ok_lat) / len(calls), 3),
                "median_ok_ms": statistics.median(ok_lat) if ok_lat else None,
                "n_calls": len(calls),
            }
        )
    return sorted(
        windows,
        key=lambda w: (w["saturation"], w["median_ok_ms"] or float("inf")),
    )


def main() -> None:
    """Aggregate the probe series and print the ranked launch windows."""
    rows = load_rows()
    stamps = len(rows)
    print(
        f"{stamps} probe calls, hours covered: "
        f"{len({h for h, _, _, _ in rows})}/24 (local Europe/Paris)\n"
    )
    hourly_table(rows)
    print(f"\nTop {WINDOW_HOURS}-hour windows (saturation asc, median ok-latency asc):")
    ranking = rank_windows(rows)
    for w in ranking[:5]:
        med = f"{w['median_ok_ms']:.0f} ms" if w["median_ok_ms"] else "no ok call"
        print(
            f"  {w['window']}  saturation {w['saturation']:.0%}  "
            f"median {med}  (n={w['n_calls']})"
        )
    if ranking:
        best = ranking[0]
        print(f"\nLaunch window by the a-priori criterion: {best['window']}")
    else:
        print("\nNo window with full data coverage — degraded mode: launch at 22:00.")


if __name__ == "__main__":
    main()
