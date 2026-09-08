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
from fastapi import Depends, FastAPI, Path, Query
from pydantic import BaseModel, Field

from valid_tva.db import connect
from valid_tva.structural import assess


class Verdict(BaseModel):
    """What the referential knows about one number, and how fresh it is."""

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "input": "be 0415-621.046",
                    "vat_number": "BE0415621046",
                    "verdict": "valid",
                    "origin": "vies",
                    "motive": None,
                    "checked_at": "2026-09-08T10:06:52.095000Z",
                    "stale": False,
                    "name": "NV PLUTO",
                    "address": "Merellaan 46\n9400 Ninove",
                }
            ]
        }
    }

    input: str = Field(description="The number exactly as received.")
    vat_number: str | None = Field(
        description="Canonical number (country prefix + national part) after"
        " normalization; null when no country could be determined."
    )
    verdict: str = Field(
        description="valid | invalid | unknown — unknown means the question"
        " could not be answered yet, never that the number is bad."
    )
    origin: str = Field(
        description="Where the verdict comes from: 'structural' (deterministic"
        " check, motive given, VIES never involved), 'vies' (observed by the"
        " verification campaign), 'never_checked' (no VIES attempt yet)."
    )
    motive: str | None = Field(
        description="Structural rejection motive (MISSING, UNKNOWN_COUNTRY,"
        " NON_EU_COUNTRY, BAD_FORMAT, BAD_CHECK_DIGIT); null otherwise."
    )
    checked_at: datetime | None = Field(
        description="VIES consultation timestamp (requestDate) backing the"
        " verdict; null when origin is not 'vies'."
    )
    stale: bool | None = Field(
        description="True when the VIES verdict is older than the freshness"
        " horizon (7 days): still served, flagged for the consumer to judge."
    )
    name: str | None = Field(
        description="Registered company name as returned by VIES, when any."
    )
    address: str | None = Field(
        description="Registered address as returned by VIES, when any."
    )


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

    @app.get(
        "/vat/{number}",
        response_model=Verdict,
        summary="Qualify one VAT number",
        description="Entry noise (spaces, dots, dashes, case) is normalized"
        " away before assessment. Every verdict is a 200 — 'invalid' is an"
        " answer, not an error. The API never calls VIES live: the structural"
        " stage is recomputed on the fly, the VIES stage is read as observed"
        " by the verification campaign.",
    )
    def check_number(
        number: str = Path(
            description="The VAT number to qualify, noise tolerated"
            " (e.g. 'fi 2660-63.69').",
        ),
        # Depends-as-default (not Annotated): with postponed annotations the
        # Annotated form becomes a string referencing the closure-local `db`,
        # which FastAPI cannot resolve at runtime.
        conn: psycopg.Connection = Depends(db),  # noqa: B008
        country: str = Query(
            default="",
            description="Declared country (ISO 3166-1 alpha-2), used only to"
            " rebuild the prefix of a number received without one.",
        ),
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
