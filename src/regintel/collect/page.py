"""Cheap sanity check that a fetched page is an FDA warning letter, not a block page."""

from __future__ import annotations

import re

_TITLE = re.compile(rb"<title>[^<]*\|\s*FDA\s*</title>", re.IGNORECASE)
_ISSUING_OFFICE = re.compile(rb"<dt[^>]*>\s*Issuing Office:?\s*</dt>", re.IGNORECASE)


def looks_like_letter(html: bytes) -> bool:
    return bool(_TITLE.search(html) and _ISSUING_OFFICE.search(html))
