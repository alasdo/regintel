"""The fda.gov warning-letter listing, read from the DataTables JSON behind the listing page."""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlsplit

from regintel.collect.http import PoliteClient
from regintel.letter_type import letter_type, normalise_subject

log = logging.getLogger(__name__)

FDA_ORIGIN = "https://www.fda.gov"
LISTING_URL = f"{FDA_ORIGIN}/datatables/views/ajax"
LISTING_PARAMS: dict[str, str | int] = {
    "view_name": "warning_letter_solr_index",
    "view_display_id": "warning_letter_solr_block",
    "draw": 1,
}
CELLS = 8  # posted, issued, company, office, subject, response, close-out, excerpt


class ListingSchemaError(ValueError):
    """The listing no longer looks like what this parser was written for."""


@dataclass(frozen=True)
class ListingRow:
    letter_id: str
    url: str
    posted_date: date
    issue_date: date | None
    company: str
    issuing_office: str  # may be "": some real in-scope rows have no office
    subject: str
    response_letter_url: str | None
    closeout_url: str | None
    closeout_date: date | None


class _Cell(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.href: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a" and self.href is None:
            self.href = dict(attrs).get("href")
        self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _cell(raw: object) -> tuple[str, str | None]:
    if not isinstance(raw, str):
        raise ListingSchemaError(f"cell is {type(raw).__name__}, not str")
    parser = _Cell()
    parser.feed(raw)
    parser.close()
    return " ".join("".join(parser.parts).split()), parser.href


def normalise_url(href: str) -> str:
    """Absolute https://www.fda.gov URL without query, fragment or trailing slash."""
    parts = urlsplit(href)
    path = parts.path.rstrip("/")
    if parts.netloc not in ("", "www.fda.gov", "fda.gov") or not path.startswith("/"):
        raise ListingSchemaError(f"unexpected link {href!r}")
    return FDA_ORIGIN + path


def _date(text: str) -> date:
    try:
        return datetime.strptime(text, "%m/%d/%Y").date()  # noqa: DTZ007 - a calendar date
    except ValueError as exc:
        raise ListingSchemaError(f"date {text!r} is not MM/DD/YYYY") from exc


def _optional_date(text: str) -> date | None:
    return _date(text) if text else None


def _row(cells: object) -> ListingRow:
    if not isinstance(cells, list) or len(cells) != CELLS:
        raise ListingSchemaError(f"row does not have {CELLS} cells: {cells!r:.200}")
    posted, _ = _cell(cells[0])
    issued, _ = _cell(cells[1])
    company, href = _cell(cells[2])
    office, _ = _cell(cells[3])
    subject = normalise_subject(cells[4]) if isinstance(cells[4], str) else ""
    _, response_href = _cell(cells[5])
    closeout_text, closeout_href = _cell(cells[6])
    if not href:
        raise ListingSchemaError(f"no letter link in company cell {cells[2]!r:.200}")
    if not subject:
        raise ListingSchemaError(f"empty subject for {href}")
    url = normalise_url(href)
    return ListingRow(
        letter_id=url.rsplit("/", 1)[1],
        url=url,
        posted_date=_date(posted),
        issue_date=_optional_date(issued),
        company=company,
        issuing_office=office,
        subject=subject,
        response_letter_url=normalise_url(response_href) if response_href else None,
        closeout_url=normalise_url(closeout_href) if closeout_href else None,
        closeout_date=_optional_date(closeout_text),
    )


def parse_listing_page(payload: object) -> tuple[int, list[ListingRow]]:
    """Validate one DataTables response; return (recordsTotal, rows in page order)."""
    if not isinstance(payload, dict):
        raise ListingSchemaError("listing payload is not an object")
    total = payload.get("recordsTotal")
    data = payload.get("data")
    if not isinstance(total, int) or isinstance(total, bool):
        raise ListingSchemaError("recordsTotal missing or not an int")
    if not isinstance(data, list):
        raise ListingSchemaError("data missing or not a list")
    return total, [_row(cells) for cells in data]


def dedupe_rows(rows: Sequence[ListingRow]) -> tuple[list[ListingRow], int]:
    """Drop identical duplicate rows (FDA's listing has some); conflicting ones are an error."""
    seen: dict[str, ListingRow] = {}
    unique: list[ListingRow] = []
    dropped = 0
    for row in rows:
        previous = seen.get(row.letter_id)
        if previous is None:
            seen[row.letter_id] = row
            unique.append(row)
        elif previous == row:
            dropped += 1
        else:
            raise ListingSchemaError(f"conflicting duplicate rows for {row.letter_id}")
    return unique, dropped


def _fetch_all_pages(client: PoliteClient, page_size: int) -> tuple[list[ListingRow], str | None]:
    """One pass over the listing; returns the rows and a reason if the pass was inconsistent."""
    rows: list[ListingRow] = []
    totals: set[int] = set()
    start = 0
    while True:
        params: dict[str, str | int] = {**LISTING_PARAMS, "start": start, "length": page_size}
        result = client.get(LISTING_URL, params=params)
        try:
            payload: Any = json.loads(result.body)
        except ValueError as exc:
            raise ListingSchemaError(f"listing page at start={start} is not JSON") from exc
        total, page = parse_listing_page(payload)
        totals.add(total)
        rows.extend(page)
        start += page_size
        if start >= total or not page:
            break
    if len(totals) != 1:
        return rows, f"recordsTotal changed while paging: {sorted(totals)}"
    if len(rows) != totals.pop():
        return rows, f"row count {len(rows)} does not match recordsTotal"
    return rows, None


def _checked_pass(client: PoliteClient, page_size: int) -> tuple[list[ListingRow], int, str | None]:
    """One pass, deduplicated; returns (rows, duplicates dropped, problem or None)."""
    rows, problem = _fetch_all_pages(client, page_size)
    if problem:
        return rows, 0, problem
    try:
        unique, dropped = dedupe_rows(rows)
    except ListingSchemaError as exc:
        return rows, 0, str(exc)
    return unique, dropped, None


MAX_PASSES = 3


def fetch_listing(client: PoliteClient, page_size: int = 500) -> tuple[list[ListingRow], int]:
    """All listing rows, deduplicated, in listing order, plus the number of duplicates dropped.

    A pass is trusted when it is internally consistent and either has no duplicates or has
    the same letter ids as the pass before it. Rows shifting across a page boundary
    mid-paging look exactly like FDA's genuine duplicate rows (and hide a missing row), so
    duplicates are only accepted once two passes agree.
    """
    previous_ids: set[str] | None = None
    problem = "no pass made"
    for attempt in range(1, MAX_PASSES + 1):
        rows, dropped, problem_or_none = _checked_pass(client, page_size)
        ids = {r.letter_id for r in rows}
        if problem_or_none is None and (dropped == 0 or ids == previous_ids):
            break
        problem = problem_or_none or f"{dropped} duplicate rows not yet confirmed"
        previous_ids = None if problem_or_none else ids
        log.warning("listing pass %d: %s; reading it again", attempt, problem)
    else:
        raise ListingSchemaError(f"listing unstable after {MAX_PASSES} passes: {problem}")
    if dropped:
        log.info("dropped %d identical duplicate listing rows (confirmed by two passes)", dropped)
    if not rows:
        raise ListingSchemaError("listing is empty: drift or a block, not 'nothing new'")
    if not any(letter_type(r.subject) for r in rows):
        raise ListingSchemaError("listing has no in-scope rows: drift or a block")
    return rows, dropped
