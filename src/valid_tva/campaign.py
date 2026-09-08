"""VIES verification campaign over the canonical numbers (decisions D5, notes/08).

The campaign selects the numbers that still need a check (never checked,
'unknown', or stale beyond stale_after_days), calls VIES through an
injectable `check(country, national) -> dict` callable (raw JSON body, or
httpx.HTTPError on transport failure), and persists one verdict per number
with an immediate commit — an interruption therefore loses nothing and the
next run picks up exactly where it stopped.

Verdict mapping (notes/08 taxonomy): `valid` true/false -> 'valid'/'invalid';
a wrapped error (`errorWrappers`) or a transport error -> 'unknown', never
'invalid' — those outcomes say nothing about the number itself.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
import psycopg
import structlog

logger = structlog.get_logger(__name__)

CheckFn = Callable[[str, str], dict]

SELECT_TARGETS = """
    SELECT vat_number, country, national
    FROM vat_numbers
    WHERE vies_status IS NULL
       OR vies_status = 'unknown'
       OR vies_checked_at < now() - make_interval(days => %s)
    ORDER BY vat_number
"""

UPDATE_VERDICT = """
    UPDATE vat_numbers
    SET vies_status = %s, vies_checked_at = %s,
        vies_name = %s, vies_address = %s
    WHERE vat_number = %s
"""


@dataclass
class CampaignSummary:
    """Per-outcome counts for one campaign run."""

    checked: int = 0
    valid: int = 0
    invalid: int = 0
    unknown: int = 0


def _absence_as_null(value: object) -> str | None:
    """Map the member-state 'no info' conventions ('---', '') to NULL."""
    return value if isinstance(value, str) and value not in ("", "---") else None


def _checked_at(body: dict) -> datetime:
    """The verdict timestamp: VIES requestDate when present, else now."""
    try:
        return datetime.fromisoformat(body["requestDate"])
    except (KeyError, TypeError, ValueError):
        return datetime.now(UTC)


def _verdict(body: dict) -> tuple[str, datetime, str | None, str | None]:
    """Map a raw VIES body onto (status, checked_at, name, address)."""
    if "valid" in body:
        status = "valid" if body["valid"] else "invalid"
        name = _absence_as_null(body.get("name"))
        address = _absence_as_null(body.get("address"))
        return status, _checked_at(body), name, address
    return "unknown", datetime.now(UTC), None, None


def run_campaign(
    conn: psycopg.Connection,
    check: CheckFn,
    *,
    limit: int | None = None,
    stale_after_days: int = 7,
    pause_s: float = 0.5,
) -> CampaignSummary:
    """Check every number needing it, one committed verdict at a time."""
    targets = conn.execute(SELECT_TARGETS, (stale_after_days,)).fetchall()
    if limit is not None:
        targets = targets[:limit]
    log = logger.bind(targets=len(targets))
    log.info("campaign_started")

    summary = CampaignSummary()
    for vat_number, country, national in targets:
        try:
            body = check(country, national)
        except httpx.HTTPError as exc:
            status, checked_at, name, address = (
                "unknown",
                datetime.now(UTC),
                None,
                None,
            )
            log.warning("transport_error", number=vat_number, error=str(exc))
        else:
            status, checked_at, name, address = _verdict(body)
            if status == "unknown":
                log.warning("wrapped_error", number=vat_number, body_keys=sorted(body))
        conn.execute(UPDATE_VERDICT, (status, checked_at, name, address, vat_number))
        conn.commit()
        summary.checked += 1
        setattr(summary, status, getattr(summary, status) + 1)
        log.info("verdict_stored", number=vat_number, status=status)
        if pause_s:
            time.sleep(pause_s)

    log.info("campaign_finished", **vars(summary))
    return summary
