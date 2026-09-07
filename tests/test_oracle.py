"""Oracle tests (decision D4): hand-rolled key checks vs python-stdnum.

python-stdnum is a TEST-ONLY dependency, used as a reference implementation
("étalon"). For every anchor we generate systematic mutations — each digit
substituted, each adjacent pair transposed — and require our verdict to agree
with the oracle's on every single one. A disagreement means a bug in our
arithmetic, which would otherwise create undetectable false invalids.

Countries whose key algorithm is not implemented (check_key returns None,
graceful degradation) are skipped, not failed.
"""

from __future__ import annotations

import pytest
from stdnum.eu import vat as oracle

from anchors import VALID_ANCHORS
from valid_tva.structural import check_format, check_key


def mutate(national: str) -> list[str]:
    """Systematic single-error mutations of a national number.

    Each digit position is replaced by (digit + 1) mod 10, and each adjacent
    digit pair is transposed — the two classic data-entry errors that check
    digits are designed to catch.
    """
    mutations = []
    chars = list(national)
    for i, char in enumerate(chars):
        if char.isdigit():
            substituted = chars.copy()
            substituted[i] = str((int(char) + 1) % 10)
            mutations.append("".join(substituted))
    for i in range(len(chars) - 1):
        if chars[i].isdigit() and chars[i + 1].isdigit() and chars[i] != chars[i + 1]:
            transposed = chars.copy()
            transposed[i], transposed[i + 1] = transposed[i + 1], transposed[i]
            mutations.append("".join(transposed))
    return mutations


@pytest.mark.parametrize(("country", "national"), VALID_ANCHORS)
def test_agreement_with_oracle_on_mutations(country: str, national: str) -> None:
    """Our (format + key) verdict must match stdnum on every mutation."""
    if check_key(country, national) is None:
        pytest.skip(f"no key algorithm implemented for {country} (D4 degradation)")
    for candidate in [national, *mutate(national)]:
        ours = check_format(country, candidate) and check_key(country, candidate)
        theirs = oracle.is_valid(country + candidate)
        assert ours == theirs, (
            f"disagreement on {country}{candidate}: ours={ours}, oracle={theirs}"
        )
