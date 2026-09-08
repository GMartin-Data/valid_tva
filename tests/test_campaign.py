"""Red integration contract for the VIES verification campaign (J2).

Database fixtures (throwaway tva_test) live in conftest.py. The campaign
never talks to the network here: it takes an injectable `check(country,
national) -> dict`
callable returning the raw VIES JSON body (shapes observed in notes/08), or
raising httpx.HTTPError for transport failures.

Contract under test (decisions D5 + notes/08 taxonomy):
- selection: never-checked (NULL), always-retryable 'unknown', and stale
  verdicts (> stale_after_days); fresh verdicts are left alone; deterministic
  ORDER BY vat_number; `limit` caps the calls (sample mode);
- mapping: valid true/false -> 'valid'/'invalid'; wrapped error or transport
  error -> 'unknown', never 'invalid'; requestDate -> vies_checked_at;
- resume: one commit per number, so an interruption keeps acquired verdicts
  and the next run only calls the remaining numbers.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import psycopg
import pytest

from valid_tva.campaign import run_campaign


def valid_body(country: str, national: str, name: str = "ACME CORP") -> dict:
    """A real-shaped VIES body for a registered number (notes/08)."""
    return {
        "countryCode": country,
        "vatNumber": national,
        "requestDate": "2026-09-08T07:38:18.378Z",
        "valid": True,
        "requestIdentifier": "",
        "name": name,
        "address": "1, RUE DE L'EXEMPLE\nL-1855  LUXEMBOURG",
        "traderName": "---",
        "traderNameMatch": "NOT_PROCESSED",
    }


def invalid_body(country: str, national: str) -> dict:
    """A real-shaped VIES body for an unregistered number (notes/08)."""
    return {
        "countryCode": country,
        "vatNumber": national,
        "requestDate": "2026-09-08T07:36:08.783Z",
        "valid": False,
        "requestIdentifier": "",
        "name": "---",
        "address": "---",
        "traderName": "---",
        "traderNameMatch": "NOT_PROCESSED",
    }


ERROR_BODY = {
    "actionSucceed": False,
    "errorWrappers": [{"error": "MS_MAX_CONCURRENT_REQ"}],
}


class RecordingCheck:
    """Fake VIES client: scripted body (or exception) per canonical number."""

    def __init__(self, script: dict[str, object]) -> None:
        """Store the per-number script; start with an empty call log."""
        self.script = script
        self.calls: list[str] = []

    def __call__(self, country: str, national: str) -> dict:
        """Log the call, then return the scripted body or raise it."""
        number = country + national
        self.calls.append(number)
        outcome = self.script[number]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def seed(
    conn: psycopg.Connection,
    number: str,
    status: str | None = None,
    checked_days_ago: int | None = None,
) -> None:
    """Insert one canonical number, optionally with a prior verdict."""
    conn.execute(
        "INSERT INTO vat_numbers (vat_number, country, national,"
        " vies_status, vies_checked_at)"
        " VALUES (%s, %s, %s, %s,"
        " CASE WHEN %s::int IS NULL THEN NULL"
        "      ELSE now() - make_interval(days => %s) END)",
        (number, number[:2], number[2:], status, checked_days_ago, checked_days_ago),
    )
    conn.commit()


def status_of(conn: psycopg.Connection, number: str) -> tuple:
    """Return (vies_status, vies_checked_at, vies_name) for one number."""
    return conn.execute(
        "SELECT vies_status, vies_checked_at, vies_name"
        " FROM vat_numbers WHERE vat_number = %s",
        (number,),
    ).fetchone()


class TestSelection:
    """Which numbers get a call — and in which order."""

    def test_only_numbers_needing_a_check_are_called(self, conn) -> None:
        """NULL, 'unknown' and stale are called; a fresh verdict is not."""
        seed(conn, "DK13585628")  # never checked
        seed(conn, "FI26606369", status="unknown", checked_days_ago=0)
        seed(conn, "LU26375245", status="valid", checked_days_ago=8)  # stale
        seed(conn, "PT50072677", status="invalid", checked_days_ago=1)  # fresh
        check = RecordingCheck(
            {
                "DK13585628": invalid_body("DK", "13585628"),
                "FI26606369": valid_body("FI", "26606369"),
                "LU26375245": valid_body("LU", "26375245"),
            }
        )
        summary = run_campaign(conn, check, pause_s=0.0)
        assert sorted(check.calls) == ["DK13585628", "FI26606369", "LU26375245"]
        assert summary.checked == 3
        assert status_of(conn, "PT50072677")[0] == "invalid"  # untouched

    def test_selection_order_is_deterministic(self, conn) -> None:
        """Numbers are called in vat_number order (resumable, predictable)."""
        for number in ("LU26375245", "DK13585628", "FI26606369"):
            seed(conn, number)
        check = RecordingCheck(
            {
                "DK13585628": invalid_body("DK", "13585628"),
                "FI26606369": invalid_body("FI", "26606369"),
                "LU26375245": invalid_body("LU", "26375245"),
            }
        )
        run_campaign(conn, check, pause_s=0.0)
        assert check.calls == ["DK13585628", "FI26606369", "LU26375245"]

    def test_limit_caps_the_calls_sample_mode(self, conn) -> None:
        """With limit=2, only the first two selected numbers are called."""
        for number in ("DK13585628", "FI26606369", "LU26375245"):
            seed(conn, number)
        check = RecordingCheck(
            {
                "DK13585628": invalid_body("DK", "13585628"),
                "FI26606369": invalid_body("FI", "26606369"),
            }
        )
        summary = run_campaign(conn, check, limit=2, pause_s=0.0)
        assert check.calls == ["DK13585628", "FI26606369"]
        assert summary.checked == 2
        assert status_of(conn, "LU26375245")[0] is None


class TestMapping:
    """From raw VIES bodies (notes/08) to persisted verdicts."""

    def test_valid_true_is_persisted_with_identity(self, conn) -> None:
        """'valid' + name + vies_checked_at taken from requestDate."""
        seed(conn, "LU26375245")
        check = RecordingCheck(
            {"LU26375245": valid_body("LU", "26375245", name="AMAZON EUROPE")}
        )
        summary = run_campaign(conn, check, pause_s=0.0)
        status, checked_at, name = status_of(conn, "LU26375245")
        assert (status, name) == ("valid", "AMAZON EUROPE")
        assert checked_at == datetime(2026, 9, 8, 7, 38, 18, 378000, tzinfo=UTC)
        assert summary.valid == 1

    def test_valid_false_is_persisted_as_invalid(self, conn) -> None:
        """'invalid', with the placeholder name left unstored."""
        seed(conn, "FR41303265045")
        check = RecordingCheck({"FR41303265045": invalid_body("FR", "41303265045")})
        summary = run_campaign(conn, check, pause_s=0.0)
        status, checked_at, name = status_of(conn, "FR41303265045")
        assert status == "invalid"
        assert checked_at is not None
        assert name is None  # '---' and '' are absences, not names
        assert summary.invalid == 1

    def test_wrapped_error_maps_to_unknown_never_invalid(self, conn) -> None:
        """MS_MAX_CONCURRENT_REQ says nothing about the number (notes/08)."""
        seed(conn, "DK61530843")
        check = RecordingCheck({"DK61530843": ERROR_BODY})
        summary = run_campaign(conn, check, pause_s=0.0)
        status, checked_at, _ = status_of(conn, "DK61530843")
        assert status == "unknown"
        assert checked_at is not None
        assert summary.unknown == 1

    def test_transport_error_maps_to_unknown(self, conn) -> None:
        """A timeout is an absence of verdict, not a verdict."""
        seed(conn, "BE0605238824")
        check = RecordingCheck({"BE0605238824": httpx.ReadTimeout("timed out")})
        summary = run_campaign(conn, check, pause_s=0.0)
        assert status_of(conn, "BE0605238824")[0] == "unknown"
        assert summary.unknown == 1


class TestResume:
    """Interruption loses nothing; the next run finishes the job."""

    def test_interruption_keeps_acquired_verdicts(self, conn) -> None:
        """Killed on the 3rd number: the first two verdicts are committed."""
        for number in ("DK13585628", "FI26606369", "LU26375245"):
            seed(conn, number)
        check = RecordingCheck(
            {
                "DK13585628": invalid_body("DK", "13585628"),
                "FI26606369": valid_body("FI", "26606369"),
                "LU26375245": KeyboardInterrupt(),
            }
        )
        with pytest.raises(KeyboardInterrupt):
            run_campaign(conn, check, pause_s=0.0)
        assert status_of(conn, "DK13585628")[0] == "invalid"
        assert status_of(conn, "FI26606369")[0] == "valid"
        assert status_of(conn, "LU26375245")[0] is None

    def test_second_run_only_calls_the_remaining_numbers(self, conn) -> None:
        """After the crash above, a fresh run skips the acquired verdicts."""
        for number in ("DK13585628", "FI26606369", "LU26375245"):
            seed(conn, number)
        first = RecordingCheck(
            {
                "DK13585628": invalid_body("DK", "13585628"),
                "FI26606369": valid_body("FI", "26606369"),
                "LU26375245": KeyboardInterrupt(),
            }
        )
        with pytest.raises(KeyboardInterrupt):
            run_campaign(conn, first, pause_s=0.0)
        second = RecordingCheck({"LU26375245": valid_body("LU", "26375245")})
        summary = run_campaign(conn, second, pause_s=0.0)
        assert second.calls == ["LU26375245"]
        assert summary.checked == 1
