"""Hand-rolled check-digit algorithms, one per country (decision D4).

Each function receives the NATIONAL part of a number whose format was already
validated, and answers: are the check digits arithmetically consistent?
Three algorithm families cover the ten countries:

- modulo on the number itself: BE (mod 97), LU (mod 89), FR (mod 97 variant);
- Luhn (double every second digit): IT, SE;
- weighted sum mod 11: DK, FI, NL, PL, PT (weights differ per country).

python-stdnum cross-checks every function on systematic mutations in
tests/test_oracle.py — a disagreement there means a bug HERE.
"""

from __future__ import annotations

from collections.abc import Callable


def _luhn(digits: str) -> bool:
    """Luhn checksum: from the right, double every second digit (minus 9 when
    above 9); the grand total must be a multiple of 10."""
    total = 0
    for position, char in enumerate(reversed(digits)):
        digit = int(char)
        if position % 2 == 1:
            digit = digit * 2 - 9 if digit > 4 else digit * 2
        total += digit
    return total % 10 == 0


def check_be(national: str) -> bool:
    """Belgium: the last two digits equal 97 minus (first eight mod 97)."""
    return 97 - int(national[:8]) % 97 == int(national[8:])


def check_dk(national: str) -> bool:
    """Denmark: weighted sum (2,7,6,5,4,3,2,1) over all eight digits ≡ 0 mod 11."""
    weights = (2, 7, 6, 5, 4, 3, 2, 1)
    total = sum(int(c) * w for c, w in zip(national, weights, strict=True))
    return total % 11 == 0


def check_fi(national: str) -> bool:
    """Finland: weighted sum (7,9,10,5,8,4,2) over the first seven digits;
    remainder 1 is forbidden, otherwise check digit = (11 - remainder) % 11."""
    weights = (7, 9, 10, 5, 8, 4, 2)
    remainder = sum(int(c) * w for c, w in zip(national[:7], weights, strict=True)) % 11
    if remainder == 1:
        return False
    return (11 - remainder) % 11 == int(national[7])


def check_fr(national: str) -> bool:
    """France: numeric key = (12 + 3 * (SIREN mod 97)) mod 97.

    Alphanumeric keys (newer scheme) are accepted unchecked: VIES remains
    the authority for them; no such number exists in the referential.
    """
    key, siren = national[:2], national[2:]
    if not key.isdigit():
        return True
    return int(key) == (12 + 3 * (int(siren) % 97)) % 97


def check_it(national: str) -> bool:
    """Italy: plain Luhn over the eleven digits."""
    return _luhn(national)


def check_lu(national: str) -> bool:
    """Luxembourg: the last two digits equal (first six) mod 89."""
    return int(national[:6]) % 89 == int(national[6:])


def check_nl(national: str) -> bool:
    """Netherlands: legacy weighted sum (9..2) mod 11 on the nine digits, OR
    (numbers issued since 2020) ISO 7064 mod 97-10 over the full identifier
    with letters mapped to numbers (A=10 ... Z=35)."""
    digits = national[:9]
    weighted = sum(int(c) * w for c, w in zip(digits[:8], range(9, 1, -1), strict=True))
    if weighted % 11 == int(digits[8]):
        return True
    translated = "".join(str(int(c, 36)) for c in f"NL{national}")
    return int(translated) % 97 == 1


def check_pl(national: str) -> bool:
    """Poland: weighted sum (6,5,7,2,3,4,5,6,7) over the first nine digits,
    mod 11, equals the tenth digit (a result of 10 is always invalid)."""
    weights = (6, 5, 7, 2, 3, 4, 5, 6, 7)
    total = sum(int(c) * w for c, w in zip(national[:9], weights, strict=True))
    return total % 11 == int(national[9])


def check_pt(national: str) -> bool:
    """Portugal: weighted sum (9..2) over the first eight digits, mod 11;
    check digit = 0 when the remainder is below 2, else 11 - remainder."""
    remainder = (
        sum(int(c) * w for c, w in zip(national[:8], range(9, 1, -1), strict=True)) % 11
    )
    check = 0 if remainder < 2 else 11 - remainder
    return check == int(national[8])


def check_se(national: str) -> bool:
    """Sweden: Luhn over the first ten digits (the trailing 01 is fixed)."""
    return _luhn(national[:10])


#: Registry consumed by structural.check_key; a country absent here is
#: simply not key-checked (graceful degradation, D4).
KEY_CHECKS: dict[str, Callable[[str], bool]] = {
    "BE": check_be,
    "DK": check_dk,
    "FI": check_fi,
    "FR": check_fr,
    "IT": check_it,
    "LU": check_lu,
    "NL": check_nl,
    "PL": check_pl,
    "PT": check_pt,
    "SE": check_se,
}
