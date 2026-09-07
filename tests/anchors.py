"""Real-world valid VAT numbers used as test anchors.

Every pair was verified against python-stdnum (the oracle) before being
written down here; test_oracle.py re-checks that agreement continuously.
"""

from __future__ import annotations

#: (country, national) pairs, all format-valid AND key-valid.
VALID_ANCHORS = [
    ("BE", "0403019261"),
    ("DK", "13585628"),
    ("FI", "20774740"),
    ("FR", "40303265045"),
    ("IT", "00743110157"),
    ("LU", "10000356"),
    ("NL", "004495445B01"),
    ("PL", "8567346215"),
    ("PT", "501964843"),
    ("SE", "556188840401"),
]
