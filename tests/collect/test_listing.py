"""Listing endpoint: parse, validate, dedupe and paginate the fda.gov DataTables JSON."""

import copy
import json
from collections.abc import Callable
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from regintel.collect.http import PoliteClient
from regintel.collect.listing import (
    LISTING_URL,
    ListingSchemaError,
    dedupe_rows,
    fetch_listing,
    normalise_url,
    parse_listing_page,
)


def _page(fixtures_dir: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        (fixtures_dir / "collect" / "listing_page.json").read_text(encoding="utf-8")
    )
    return data


def test_parse_listing_page_golden(fixtures_dir: Path) -> None:
    total, rows = parse_listing_page(_page(fixtures_dir))
    expected = json.loads(
        (fixtures_dir / "collect" / "listing_page.expected.json").read_text(encoding="utf-8")
    )
    got = [
        {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in asdict(r).items()}
        for r in rows
    ]
    assert total == 14
    assert got == expected


def _broken(fixtures_dir: Path, mutate: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    page = copy.deepcopy(_page(fixtures_dir))
    mutate(page)
    return page


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda p: p["data"][0].pop(), id="seven-cells"),
        pytest.param(lambda p: p["data"][0].__setitem__(2, "kdc/one"), id="missing-href"),
        pytest.param(lambda p: p["data"][0].__setitem__(0, "2026-09-22"), id="bad-date"),
        pytest.param(lambda p: p["data"][0].__setitem__(4, " <br /> "), id="empty-subject"),
        pytest.param(lambda p: p.pop("recordsTotal"), id="no-records-total"),
        pytest.param(lambda p: p.__setitem__("data", "nope"), id="data-not-list"),
    ],
)
def test_schema_drift_fails(fixtures_dir: Path, mutate: Callable[[dict[str, Any]], None]) -> None:
    with pytest.raises(ListingSchemaError):
        parse_listing_page(_broken(fixtures_dir, mutate))


def test_empty_office_allowed(fixtures_dir: Path) -> None:
    _, rows = parse_listing_page(_page(fixtures_dir))
    assert any(r.issuing_office == "" for r in rows)


def test_identical_duplicates_dropped_conflicting_raise(fixtures_dir: Path) -> None:
    _, rows = parse_listing_page(_page(fixtures_dir))
    unique, dropped = dedupe_rows(rows)
    assert (len(unique), dropped) == (13, 1)
    assert len({r.letter_id for r in unique}) == 13
    conflicting = [*unique, replace(unique[0], subject="Changed")]
    with pytest.raises(ListingSchemaError, match=unique[0].letter_id):
        dedupe_rows(conflicting)


def _pages(fixtures_dir: Path, size: int, total: int | None = None) -> list[dict[str, Any]]:
    page = _page(fixtures_dir)
    data = page["data"]
    out = []
    for start in range(0, len(data), size):
        out.append(
            {
                "draw": 1,
                "recordsTotal": total if total is not None else len(data),
                "recordsFiltered": len(data),
                "data": data[start : start + size],
            }
        )
    return out


def _serve(pages_by_pass: list[list[dict[str, Any]]], size: int) -> respx.Route:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        start = int(request.url.params["start"])
        assert int(request.url.params["length"]) == size
        assert request.url.params["view_name"] == "warning_letter_solr_index"
        index = start // size
        pass_no = min(calls["n"] // len(pages_by_pass[0]), len(pages_by_pass) - 1)
        calls["n"] += 1
        return httpx.Response(200, json=pages_by_pass[pass_no][index])

    return respx.get(LISTING_URL).mock(side_effect=handler)


@respx.mock
def test_fetch_listing_paginates(
    fixtures_dir: Path, make_client: Callable[[], PoliteClient]
) -> None:
    route = _serve([_pages(fixtures_dir, 5)], 5)
    rows, dropped = fetch_listing(make_client(), page_size=5)
    assert route.call_count == 3
    expected, expected_dropped = dedupe_rows(parse_listing_page(_page(fixtures_dir))[1])
    assert rows == expected  # page order kept; identical Lone Pine Farm duplicate dropped
    assert (len(rows), dropped) == (13, expected_dropped) == (13, 1)


@respx.mock
def test_fetch_listing_detects_shift_then_recovers(
    fixtures_dir: Path, make_client: Callable[[], PoliteClient]
) -> None:
    shifted = _pages(fixtures_dir, 5)
    shifted[2] = {**shifted[2], "recordsTotal": 15}  # a letter was posted mid-paging
    route = _serve([shifted, _pages(fixtures_dir, 5)], 5)
    assert len(fetch_listing(make_client(), page_size=5)[0]) == 13
    assert route.call_count == 6


@respx.mock
def test_fetch_listing_raises_when_shift_persists(
    fixtures_dir: Path, make_client: Callable[[], PoliteClient]
) -> None:
    short = _pages(fixtures_dir, 5, total=15)  # recordsTotal says 15, only 14 rows served
    route = _serve([short], 5)
    with pytest.raises(ListingSchemaError, match="row count"):
        fetch_listing(make_client(), page_size=5)
    assert route.call_count == 6  # 3 pages (start=0,5,10) x 2 passes


@respx.mock
def test_empty_listing_fails(make_client: Callable[[], PoliteClient]) -> None:
    respx.get(LISTING_URL).mock(
        return_value=httpx.Response(200, json={"recordsTotal": 0, "data": []})
    )
    with pytest.raises(ListingSchemaError, match="empty"):
        fetch_listing(make_client(), page_size=5)


@respx.mock
def test_no_in_scope_rows_fails(
    fixtures_dir: Path, make_client: Callable[[], PoliteClient]
) -> None:
    page = _page(fixtures_dir)
    out_of_scope = [r for r in page["data"] if "Medical Devices" in r[4]]
    respx.get(LISTING_URL).mock(
        return_value=httpx.Response(200, json={"recordsTotal": 1, "data": out_of_scope})
    )
    with pytest.raises(ListingSchemaError, match="in-scope"):
        fetch_listing(make_client(), page_size=5)


@pytest.mark.parametrize(
    ("href", "expected"),
    [
        ("/a/b-1-01012024", "https://www.fda.gov/a/b-1-01012024"),
        ("/a/b-1-01012024/?x=1#top", "https://www.fda.gov/a/b-1-01012024"),
        ("http://www.fda.gov/a/B-1", "https://www.fda.gov/a/B-1"),
    ],
)
def test_normalise_url(href: str, expected: str) -> None:
    assert normalise_url(href) == expected


def test_normalise_url_rejects_foreign_host() -> None:
    with pytest.raises(ListingSchemaError):
        normalise_url("https://evil.example/a")
