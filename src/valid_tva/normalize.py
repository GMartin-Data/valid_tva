"""Normalization of raw VAT numbers: cleanup, missing detection, canonical form.

Design decisions (see docs/architecture.md):
- D1: numbers lacking a country prefix are rebuilt from the declared country,
  with the deduction traced (``prefix_added``).
- Emptiness is detected both before and after normalization (a ``NU.LL``
  entry only reveals itself once cleaned).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

EMPTY_FORMS = frozenset({"", "N/A", "NA", "NULL", "NONE", "-"})

_NON_ALNUM = re.compile(r"[^A-Z0-9]")


@dataclass(frozen=True)
class CanonicalNumber:
    """A VAT number reduced to its canonical identity: country + national part.

    Attributes:
        country: two-letter country code (upper case).
        national: the national part of the number (no country prefix).
        prefix_added: True when the country prefix was absent from the raw
            value and rebuilt from the declared country (decision D1).
    """

    country: str
    national: str
    prefix_added: bool

    @property
    def full(self) -> str:
        """Full canonical number, e.g. ``FR40303265045`` (deduplication key, D2)."""
        return self.country + self.national


def normalize(value: str) -> str:
    """Uppercase and drop every character that is not A-Z or 0-9."""
    return _NON_ALNUM.sub("", value.upper())


def is_missing(value: str) -> bool:
    """True when the value is one of the observed forms of emptiness.

    Detection applies to the stripped upper-cased value AND to the
    normalized value, so disguised forms like ``NU.LL`` are caught too.
    """
    return value.strip().upper() in EMPTY_FORMS or normalize(value) in EMPTY_FORMS


def canonicalize(raw: str, declared_country: str) -> CanonicalNumber | None:
    """Turn a raw number and its declared country into a canonical number.

    Returns None when the raw value is a form of emptiness. When the
    normalized value starts with two letters, they are taken as the country
    prefix; otherwise the declared country is used and ``prefix_added`` is
    set (decision D1).
    """
    if is_missing(raw):
        return None
    cleaned = normalize(raw)
    if cleaned[:2].isalpha():
        return CanonicalNumber(
            country=cleaned[:2], national=cleaned[2:], prefix_added=False
        )
    return CanonicalNumber(
        country=normalize(declared_country), national=cleaned, prefix_added=True
    )
