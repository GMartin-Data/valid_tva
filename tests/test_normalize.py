"""Contract tests for valid_tva.normalize, built from real referential findings.

Every noisy example below was observed in data/numeros_tva.csv (see
docs/journal.md, J1 exploration).
"""

from __future__ import annotations

import pytest

from valid_tva.normalize import CanonicalNumber, canonicalize, is_missing, normalize


class TestNormalize:
    """Cleanup: uppercase, strip everything that is not A-Z / 0-9."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("  NL505862176B88 ", "NL505862176B88"),  # padding spaces
            ("DK 7170 4289", "DK71704289"),  # inner grouping spaces
            ("SE.751298146001", "SE751298146001"),  # dots
            ("SE-353056663101", "SE353056663101"),  # dashes
            ("dk91970813", "DK91970813"),  # lowercase
            ("nl785427788b39", "NL785427788B39"),  # lowercase with letter inside
            ("FR40303265045", "FR40303265045"),  # already clean: unchanged
        ],
    )
    def test_cleans_observed_noise(self, raw: str, expected: str) -> None:
        """Observed noisy inputs are cleaned; clean input is untouched."""
        assert normalize(raw) == expected


class TestIsMissing:
    """Emptiness detection, including forms disguised by noise."""

    @pytest.mark.parametrize(
        "raw",
        ["", " ", "-", "N/A", "null", "NULL", "n/a", "NU.LL"],
    )
    def test_observed_empty_forms(self, raw: str) -> None:
        """All observed forms of emptiness are detected (NU.LL via normalization)."""
        assert is_missing(raw) is True

    @pytest.mark.parametrize("raw", ["DK73224645", "58560322811", "0"])
    def test_actual_values_are_not_missing(self, raw: str) -> None:
        """Real numbers, even a lone digit, are not emptiness."""
        assert is_missing(raw) is False


class TestCanonicalize:
    """Canonical identity: country + national part, with traced prefix rebuild (D1)."""

    def test_prefixed_number_keeps_its_prefix(self) -> None:
        """A number carrying its country prefix is split, nothing deduced."""
        assert canonicalize("DK73224645", "DK") == CanonicalNumber(
            country="DK", national="73224645", prefix_added=False
        )

    def test_missing_prefix_rebuilt_from_declared_country(self) -> None:
        """D1: prefix rebuilt from pays_declare, deduction traced."""
        assert canonicalize("58560322811", "FR") == CanonicalNumber(
            country="FR", national="58560322811", prefix_added=True
        )

    def test_inner_letter_does_not_count_as_prefix(self) -> None:
        """Only two LEADING letters form a prefix (NL national part has a B)."""
        result = canonicalize("396904956B68", "NL")
        assert result == CanonicalNumber(
            country="NL", national="396904956B68", prefix_added=True
        )

    def test_noise_cleaned_before_prefix_detection(self) -> None:
        """Prefix detection happens on the normalized value, not the raw one."""
        assert canonicalize("  dk.91970813 ", "DK") == CanonicalNumber(
            country="DK", national="91970813", prefix_added=False
        )

    def test_missing_value_yields_none(self) -> None:
        """Emptiness (even disguised) cannot be canonicalized."""
        assert canonicalize("NU.LL", "BE") is None

    def test_declared_country_is_case_insensitive(self) -> None:
        """A sloppy declared country still rebuilds a clean prefix."""
        result = canonicalize("73224645", "dk")
        assert result is not None
        assert result.country == "DK"

    def test_full_is_the_deduplication_key(self) -> None:
        """D2: the canonical full string is the dedup key across variants."""
        variants = ["DK 7170 4289", "DK.71704289", "dk71704289", "71704289"]
        fulls = {canonicalize(raw, "DK").full for raw in variants}  # type: ignore[union-attr]
        assert fulls == {"DK71704289"}
