"""Structural validation: country, per-country format, then check digit.

Three nested sieves (design note: decision D4). A rejected number carries the
motive of the FIRST sieve that stopped it. A number passing every sieve is
only a *candidate*: structure never proves validity — only VIES can tell
whether the number is actually assigned.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from valid_tva import keys
from valid_tva.normalize import canonicalize

#: EU member state codes as VIES knows them (Greece is EL, not GR;
#: XI is Northern Ireland, still in scope post-Brexit).
EU_VAT_COUNTRIES = frozenset(
    {
        "AT",
        "BE",
        "BG",
        "CY",
        "CZ",
        "DE",
        "DK",
        "EE",
        "EL",
        "ES",
        "FI",
        "FR",
        "HR",
        "HU",
        "IE",
        "IT",
        "LT",
        "LU",
        "LV",
        "MT",
        "NL",
        "PL",
        "PT",
        "RO",
        "SE",
        "SI",
        "SK",
        "XI",
    }
)

#: Real countries that left the EU VAT area (decision D3: GB post-Brexit;
#: UK was never a valid VAT prefix but designates the same situation).
NON_EU_COUNTRIES = frozenset({"GB", "UK"})


class Motive(StrEnum):
    """Rejection motives, one per sieve (order matters: first hit wins)."""

    MISSING = "MISSING"
    UNKNOWN_COUNTRY = "UNKNOWN_COUNTRY"
    NON_EU_COUNTRY = "NON_EU_COUNTRY"
    BAD_FORMAT = "BAD_FORMAT"
    BAD_CHECK_DIGIT = "BAD_CHECK_DIGIT"


@dataclass(frozen=True)
class Assessment:
    """Structural verdict for one raw referential value.

    Attributes:
        raw: the value exactly as received.
        normalized: canonical full number (country + national), None if missing.
        country: country prefix retained, None if missing.
        prefix_added: True when the prefix was rebuilt from the declared
            country (D1); False otherwise.
        candidate: True when every sieve passed — the number is worth a VIES
            call. False means rejected, and ``motive`` says why.
        motive: rejection motive, None when ``candidate`` is True.
    """

    raw: str
    normalized: str | None
    country: str | None
    prefix_added: bool
    candidate: bool
    motive: Motive | None


#: Per-country pattern of the NATIONAL part (prefix excluded). Sources:
#: European Commission VAT number structures. FR: 2-char key where letters
#: I and O are excluded to avoid confusion with 1 and 0.
FORMATS: dict[str, re.Pattern[str]] = {
    "BE": re.compile(r"[01]\d{9}"),
    "DK": re.compile(r"\d{8}"),
    "FI": re.compile(r"\d{8}"),
    "FR": re.compile(r"[0-9A-HJ-NP-Z]{2}\d{9}"),
    "IT": re.compile(r"\d{11}"),
    "LU": re.compile(r"\d{8}"),
    "NL": re.compile(r"\d{9}B\d{2}"),
    "PL": re.compile(r"\d{10}"),
    "PT": re.compile(r"\d{9}"),
    "SE": re.compile(r"\d{10}01"),
}

#: Hand-rolled check-digit validators (valid_tva.keys, D4). A country
#: absent from this registry is NOT key-checked (graceful degradation).
KEY_CHECKS: dict[str, Callable[[str], bool]] = keys.KEY_CHECKS


def check_format(country: str, national: str) -> bool:
    """True when the national part matches the country's expected pattern.

    Countries without an implemented pattern are accepted (graceful
    degradation, D4): the cost is a few extra VIES calls, never a wrong
    verdict.
    """
    pattern = FORMATS.get(country)
    return pattern is None or pattern.fullmatch(national) is not None


def check_key(country: str, national: str) -> bool | None:
    """Verify the country's check-digit scheme on a format-valid national part.

    Returns:
        True when the check digits are consistent, False when they are not,
        None when no algorithm is implemented for this country (graceful
        degradation, D4: the number stays a candidate).
    """
    validator = KEY_CHECKS.get(country)
    return None if validator is None else validator(national)


def assess(raw: str, declared_country: str) -> Assessment:
    """Run the full sieve chain on one raw value and return its assessment.

    Sieve order: missing -> country known -> country in EU -> format ->
    check digit. The first failing sieve sets the motive; a value passing
    everything is a VIES candidate.
    """

    def rejected(motive: Motive, canonical=None) -> Assessment:
        """Build a rejection carrying whatever canonical info we have."""
        return Assessment(
            raw=raw,
            normalized=canonical.full if canonical else None,
            country=canonical.country if canonical else None,
            prefix_added=canonical.prefix_added if canonical else False,
            candidate=False,
            motive=motive,
        )

    canonical = canonicalize(raw, declared_country)
    if canonical is None:
        return rejected(Motive.MISSING)
    if canonical.country in NON_EU_COUNTRIES:
        return rejected(Motive.NON_EU_COUNTRY, canonical)
    if canonical.country not in EU_VAT_COUNTRIES:
        return rejected(Motive.UNKNOWN_COUNTRY, canonical)
    if not check_format(canonical.country, canonical.national):
        return rejected(Motive.BAD_FORMAT, canonical)
    if check_key(canonical.country, canonical.national) is False:
        return rejected(Motive.BAD_CHECK_DIGIT, canonical)
    return Assessment(
        raw=raw,
        normalized=canonical.full,
        country=canonical.country,
        prefix_added=canonical.prefix_added,
        candidate=True,
        motive=None,
    )
