"""Contract tests for the structural sieves (decision D4, notes 02/04).

Anchor numbers below are real-world valid VAT numbers, every one verified
against python-stdnum (the test oracle) before being written down here.
"""

from __future__ import annotations

import pytest

from anchors import VALID_ANCHORS
from valid_tva.structural import Motive, assess, check_format, check_key


class TestCountrySieve:
    """Sieve 0 and 1: emptiness, unknown countries, non-EU countries."""

    def test_missing_value(self) -> None:
        """An empty (even disguised) value is rejected as MISSING."""
        result = assess("NU.LL", "BE")
        assert result.candidate is False
        assert result.motive is Motive.MISSING
        assert result.normalized is None

    @pytest.mark.parametrize("raw", ["ZZ23140153", "QQ72558658", "XX82647147"])
    def test_fantasy_country_codes(self, raw: str) -> None:
        """ZZ/QQ/XX do not exist in the EU: UNKNOWN_COUNTRY."""
        result = assess(raw, raw[:2])
        assert result.candidate is False
        assert result.motive is Motive.UNKNOWN_COUNTRY

    @pytest.mark.parametrize("raw", ["GB983761159", "UK227979060"])
    def test_post_brexit_codes(self, raw: str) -> None:
        """D3: GB/UK are real but out of the EU VAT area: NON_EU_COUNTRY."""
        result = assess(raw, raw[:2])
        assert result.candidate is False
        assert result.motive is Motive.NON_EU_COUNTRY

    def test_first_sieve_wins(self) -> None:
        """A missing value declared under a fantasy country is MISSING, not
        UNKNOWN_COUNTRY: sieve order is part of the contract."""
        assert assess("N/A", "ZZ").motive is Motive.MISSING


class TestFormatSieve:
    """Sieve 2: per-country length and pattern."""

    @pytest.mark.parametrize(("country", "national"), VALID_ANCHORS)
    def test_valid_anchors_pass(self, country: str, national: str) -> None:
        """Every oracle-verified anchor satisfies its country's format."""
        assert check_format(country, national) is True

    @pytest.mark.parametrize(
        ("country", "national"),
        [
            ("BE", "403019261"),  # 9 digits, must be 10
            ("BE", "2403019261"),  # must start with 0 or 1
            ("DK", "1358562"),  # 7 digits, must be 8
            ("DK", "135856281"),  # 9 digits
            ("DK", "1358562A"),  # letter where digit expected
            ("FI", "207747401"),  # 9 digits, must be 8
            ("FR", "4030326504"),  # 10 chars, must be 11
            ("FR", "IO303265045"),  # I and O forbidden in the key
            ("IT", "007431101571"),  # 12 digits, must be 11
            ("LU", "100003561"),  # 9 digits, must be 8
            ("NL", "004495445001"),  # missing the B separator
            ("NL", "004495445B1"),  # suffix must be 2 digits
            ("PL", "856734621"),  # 9 digits, must be 10
            ("PT", "50196484"),  # 8 digits, must be 9
            ("SE", "55618884040"),  # 11 digits, must be 12
            ("SE", "556188840402"),  # must end with 01
        ],
    )
    def test_impossible_shapes_rejected(self, country: str, national: str) -> None:
        """Shapes that no VAT number of that country can have are rejected."""
        assert check_format(country, national) is False


class TestKeySieve:
    """Sieve 3: check-digit arithmetic, hand-rolled per country."""

    @pytest.mark.parametrize(("country", "national"), VALID_ANCHORS)
    def test_valid_anchors_pass(self, country: str, national: str) -> None:
        """Every oracle-verified anchor has consistent check digits."""
        assert check_key(country, national) is True

    @pytest.mark.parametrize(
        ("country", "national"),
        [
            ("BE", "0403019262"),  # check pair broken
            ("DK", "13585629"),  # weighted mod 11 broken
            ("FI", "20774741"),
            ("FR", "40303265046"),  # SIREN changed, key 40 no longer matches
            ("IT", "00743110158"),  # Luhn broken
            ("LU", "10000357"),
            ("NL", "004495446B01"),  # 9th digit changed, mod 11 broken
            ("PL", "8567346216"),
            ("PT", "501964844"),
            ("SE", "556188840501"),  # Luhn digit (10th) changed, still ends 01
        ],
    )
    def test_single_digit_error_detected(self, country: str, national: str) -> None:
        """Each anchor with one digit altered fails its country's key check."""
        assert check_key(country, national) is False


class TestAssessIntegration:
    """The full chain on realistic inputs."""

    def test_clean_anchor_is_candidate(self) -> None:
        """A noisy-but-real valid number comes out a VIES candidate."""
        result = assess("fr 40 303 265 045", "FR")
        assert result.candidate is True
        assert result.motive is None
        assert result.normalized == "FR40303265045"
        assert result.prefix_added is False

    def test_rebuilt_prefix_flows_through(self) -> None:
        """D1: an anchor without prefix is rebuilt, traced, and still assessed."""
        result = assess("40303265045", "FR")
        assert result.candidate is True
        assert result.prefix_added is True
        assert result.normalized == "FR40303265045"

    def test_rejection_carries_normalized_value(self) -> None:
        """A structurally rejected number still exposes its canonical form."""
        result = assess("DK 1358562", "DK")
        assert result.candidate is False
        assert result.motive is Motive.BAD_FORMAT
        assert result.normalized == "DK1358562"
