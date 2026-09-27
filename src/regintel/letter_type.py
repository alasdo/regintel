"""Letter type from the listing subject line: the single source of scope and type rules.

The collector fetches only letters whose subject maps to a type; `parse` reuses the same
function to set `letter_type`. Rules are ordered and the first match wins. Changing a rule
means bumping RULES_VERSION and updating the pinned hash and golden table in the tests.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
from typing import Literal

LetterType = Literal["cgmp_finished", "api", "compounding", "unapproved_misbranded"]

RULES_VERSION = 1
# Bump when normalise_subject changes: it decides what the patterns see.
NORMALISER_VERSION = 1

# Subjects about other product areas are out of scope even when they mention CGMP or drugs.
_EXCLUDE = (
    r"Medical Device|QSR|Biologic|Blood|HCT/P|Tobacco|Food|Feed|Dietary|Seafood|Juice|Infant|Water"
)

_RULES: tuple[tuple[LetterType, str], ...] = (
    ("compounding", r"Compound|Outsourcing|503[AB]"),
    ("api", r"CGMP.*(Active Pharmaceutical Ingredient|\bAPI\b)"),
    (
        "cgmp_finished",
        r"CGMP.*(Finished (Pharmaceutical|Drug)|\bOTC\b|\bDrugs?\b|Drug Products|\bPET\b)",
    ),
    ("unapproved_misbranded", r"Finished Pharmaceutical.*(Unapproved|Misbrand)"),
)

_EXCLUDE_RX = re.compile(_EXCLUDE, re.IGNORECASE)
_RULES_RX = tuple((name, re.compile(rx, re.IGNORECASE)) for name, rx in _RULES)
_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")


def normalise_subject(subject: str) -> str:
    """Unescape entities, drop tags and collapse whitespace, as listed on fda.gov."""
    return _SPACE.sub(" ", html.unescape(_TAG.sub(" ", subject))).strip()


def letter_type(subject: str) -> LetterType | None:
    """Map a subject line to a letter type; None means out of scope."""
    text = normalise_subject(subject)
    if not text or _EXCLUDE_RX.search(text):
        return None
    for name, rx in _RULES_RX:
        if rx.search(text):
            return name
    return None


def rules_sha256() -> str:
    """Hash of the rule table (patterns, order, flags, normaliser version), recorded per fetch."""
    payload = json.dumps(
        {
            "exclude": _EXCLUDE,
            "rules": _RULES,
            "flags": "IGNORECASE",
            "normaliser_version": NORMALISER_VERSION,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()
