"""REST API: verdict + origin + freshness for one VAT number (decision D5).

The API never calls VIES. The structural stage is recomputed live (the
module is deterministic, so a verdict needs no storage), and the VIES stage
is read from the database as observed by the campaign. Freshness is exposed,
never enforced: a stale verdict is served with ``stale: true`` (D5 — the
consumer decides, the API does not withhold what it knows).

Run: uv run uvicorn --factory valid_tva.api:app
(the factory wires the app to the referential database; tests inject their
own connection factory through ``create_app``).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta

import psycopg
from fastapi import Depends, FastAPI
from pydantic import BaseModel

from valid_tva.db import connect
from valid_tva.structural import assess


class Verdict(BaseModel):
    """What the referential knows about one number, and how fresh it is."""

    input: str
    vat_number: str | None
    verdict: str
    origin: str
    motive: str | None
    checked_at: datetime | None
    stale: bool | None
    name: str | None
    address: str | None


def create_app(
    get_conn: Callable[[], psycopg.Connection],
    stale_after_days: int = 7,
) -> FastAPI:
    """Build the app around an injectable database connection factory."""
    app = FastAPI(
        title="valid_tva",
        description="Intra-EU VAT qualification: verdict, origin, freshness.",
    )

    def db() -> Iterator[psycopg.Connection]:
        """One connection per request, closed afterwards."""
        conn = get_conn()
        try:
            yield conn
        finally:
            conn.close()

    @app.get("/vat/{number}", response_model=Verdict)
    def check_number(
        number: str,
        # Depends-as-default (not Annotated): with postponed annotations the
        # Annotated form becomes a string referencing the closure-local `db`,
        # which FastAPI cannot resolve at runtime.
        conn: psycopg.Connection = Depends(db),  # noqa: B008
        country: str = "",
    ) -> Verdict:
        """Assess structure live, then read the observed VIES verdict."""
        result = assess(number, country)
        if not result.candidate:
            return Verdict(
                input=number,
                vat_number=result.normalized,
                verdict="invalid",
                origin="structural",
                motive=str(result.motive),
                checked_at=None,
                stale=None,
                name=None,
                address=None,
            )

        row = conn.execute(
            "SELECT vies_status, vies_checked_at, vies_name, vies_address"
            " FROM vat_numbers WHERE vat_number = %s",
            (result.normalized,),
        ).fetchone()
        status, checked_at, name, address = row or (None, None, None, None)
        if status is None:
            return Verdict(
                input=number,
                vat_number=result.normalized,
                verdict="unknown",
                origin="never_checked",
                motive=None,
                checked_at=None,
                stale=None,
                name=None,
                address=None,
            )

        horizon = datetime.now(UTC) - timedelta(days=stale_after_days)
        return Verdict(
            input=number,
            vat_number=result.normalized,
            verdict=status,
            origin="vies",
            motive=None,
            checked_at=checked_at,
            stale=checked_at < horizon,
            name=name,
            address=address,
        )

    return app


def app() -> FastAPI:
    """Uvicorn factory entry point, wired to the referential database."""
    return create_app(connect)
