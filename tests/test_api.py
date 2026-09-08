"""Red integration contract for the REST API (J2 afternoon).

Database fixtures (throwaway tva_test) and the shared `seed` helper live in
conftest.py. The app is built by an injectable factory (`create_app(get_conn)`)
so these tests point it at the throwaway database; the API itself NEVER calls
VIES (decision D5) — it recomputes the structural stage live (deterministic
module) and reads the observed VIES stage from the database.

Contract under test:
- every verdict is an HTTP 200 (invalid is an answer, not an error);
- origin says where the verdict comes from: 'structural' (rejected before
  VIES), 'vies' (observed verdict, 'unknown' included), 'never_checked'
  (candidate without a VIES attempt yet — referential backlog and numbers
  foreign to the referential alike);
- freshness (D5): checked_at echoed, stale=true beyond 7 days, verdict
  still served;
- normalization live (noise is not invalidity) and ?country=XX rebuilding a
  missing prefix (D1 counterpart for the API).
"""

from __future__ import annotations

import psycopg
import pytest
from fastapi.testclient import TestClient

from conftest import TEST_DB, seed
from valid_tva.api import create_app
from valid_tva.db import connect


@pytest.fixture
def client(conn: psycopg.Connection) -> TestClient:
    """App wired to the throwaway database (fresh connection per request)."""
    return TestClient(create_app(lambda: connect(TEST_DB)))


class TestViesVerdicts:
    """Candidates whose verdict comes from the observed VIES stage."""

    def test_valid_number_with_identity_and_freshness(self, conn, client) -> None:
        """valid + origin vies + fresh timestamp + registered identity."""
        seed(
            conn,
            "LU26375245",
            status="valid",
            checked_days_ago=0,
            name="AMAZON EUROPE",
            address="KENNEDY 38",
        )
        resp = client.get("/vat/LU26375245")
        assert resp.status_code == 200
        body = resp.json()
        assert body["verdict"] == "valid"
        assert body["origin"] == "vies"
        assert body["vat_number"] == "LU26375245"
        assert body["motive"] is None
        assert body["stale"] is False
        assert body["checked_at"] is not None
        assert body["name"] == "AMAZON EUROPE"

    def test_invalid_number(self, conn, client) -> None:
        """valid=false at VIES -> verdict invalid, origin vies."""
        seed(conn, "FI26606369", status="invalid", checked_days_ago=0)
        body = client.get("/vat/FI26606369").json()
        assert (body["verdict"], body["origin"]) == ("invalid", "vies")

    def test_unknown_status_is_a_verdict_of_its_own(self, conn, client) -> None:
        """'unknown' (VIES could not answer) is served as such, origin vies."""
        seed(conn, "DK13585628", status="unknown", checked_days_ago=0)
        body = client.get("/vat/DK13585628").json()
        assert (body["verdict"], body["origin"]) == ("unknown", "vies")

    def test_stale_verdict_is_served_and_flagged(self, conn, client) -> None:
        """D5: beyond 7 days the verdict is still served, with stale=true."""
        seed(conn, "LU26375245", status="valid", checked_days_ago=8)
        body = client.get("/vat/LU26375245").json()
        assert body["verdict"] == "valid"
        assert body["stale"] is True

    def test_never_checked_candidate(self, conn, client) -> None:
        """In the referential, structurally fine, no VIES attempt yet."""
        seed(conn, "PT787327239")
        body = client.get("/vat/PT787327239").json()
        assert (body["verdict"], body["origin"]) == ("unknown", "never_checked")
        assert body["checked_at"] is None
        assert body["stale"] is None


class TestStructuralVerdicts:
    """Numbers rejected before the VIES stage: live deterministic verdict."""

    def test_bad_check_digit(self, client) -> None:
        """Wrong key -> invalid, origin structural, motive exposed."""
        body = client.get("/vat/FR41303265045").json()
        assert (body["verdict"], body["origin"]) == ("invalid", "structural")
        assert body["motive"] == "BAD_CHECK_DIGIT"
        assert body["checked_at"] is None

    def test_gb_is_non_eu_not_unknown_country(self, client) -> None:
        """D3: GB -> invalid with NON_EU_COUNTRY, never sent to VIES."""
        body = client.get("/vat/GB983761159").json()
        assert (body["verdict"], body["origin"]) == ("invalid", "structural")
        assert body["motive"] == "NON_EU_COUNTRY"

    def test_unknown_country_prefix(self, client) -> None:
        """ZZ -> invalid with UNKNOWN_COUNTRY (distinct from NON_EU, D3)."""
        body = client.get("/vat/ZZ12345678").json()
        assert (body["verdict"], body["origin"]) == ("invalid", "structural")
        assert body["motive"] == "UNKNOWN_COUNTRY"


class TestLookupEdges:
    """Inputs beyond the referential's happy path."""

    def test_noisy_input_resolves_to_canonical(self, conn, client) -> None:
        """'fi 2660-63.69' reaches the FI26606369 verdict (noise != invalid)."""
        seed(conn, "FI26606369", status="valid", checked_days_ago=0)
        body = client.get("/vat/fi 2660-63.69").json()
        assert body["vat_number"] == "FI26606369"
        assert body["verdict"] == "valid"

    def test_missing_prefix_rebuilt_from_country_param(self, conn, client) -> None:
        """D1 counterpart: /vat/26606369?country=FI hits the FI number."""
        seed(conn, "FI26606369", status="invalid", checked_days_ago=0)
        body = client.get("/vat/26606369", params={"country": "FI"}).json()
        assert body["vat_number"] == "FI26606369"
        assert (body["verdict"], body["origin"]) == ("invalid", "vies")

    def test_candidate_foreign_to_the_referential(self, client) -> None:
        """Structurally fine but absent from the base: unknown/never_checked."""
        body = client.get("/vat/FR40303265045").json()
        assert (body["verdict"], body["origin"]) == ("unknown", "never_checked")

    def test_openapi_schema_is_served(self, client) -> None:
        """The OpenAPI document is available (brief deliverable)."""
        assert client.get("/openapi.json").status_code == 200
