"""Manifest and skip lines: strict schema, canonical JSONL, no duplicate versions."""

from datetime import UTC, date, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from regintel.collect.manifest import (
    ListingFields,
    ManifestError,
    ManifestLine,
    parse_manifest,
    serialise,
)

SHA = "a" * 64


def line(letter_id: str = "x-1-01012024", sha: str = SHA, **kw: object) -> ManifestLine:
    fields = {
        "schema_version": 1,
        "letter_id": letter_id,
        "url": f"https://www.fda.gov/w/{letter_id}",
        "retrieved_at": datetime(2026, 9, 27, 12, tzinfo=UTC),
        "sha256": sha,
        "bytes": 10,
        "http_status": 200,
        "path": f"raw/letters/{letter_id}/{sha}.html",
        "listing": ListingFields(
            posted_date=date(2026, 9, 22),
            issue_date=None,
            company="Firm & Co",
            issuing_office="",
            subject="CGMP/Finished Pharmaceuticals/Adulterated",
            response_letter_url=None,
            closeout_url=None,
            closeout_date=None,
        ),
        "letter_type": "cgmp_finished",
        "rules_version": 1,
        "rules_sha256": "b" * 64,
        "run_id": "20260927T120000Z-0000abcd",
        "collector_version": "0.1.0",
    }
    fields.update(kw)
    return ManifestLine.model_validate(fields)


def test_round_trip_is_canonical() -> None:
    lines = [line(), line("y-2-01012024")]
    text = serialise(lines)
    assert text.endswith("\n") and text.count("\n") == 2
    assert parse_manifest(text) == lines
    assert serialise(parse_manifest(text)) == text
    assert text.index('"bytes"') < text.index('"letter_id"')  # sorted keys


def test_duplicate_version_rejected() -> None:
    with pytest.raises(ManifestError, match="duplicate"):
        parse_manifest(serialise([line(), line()]))


def test_empty_manifest() -> None:
    assert parse_manifest("") == []


@pytest.mark.parametrize(
    "bad",
    [
        {"retrieved_at": datetime(2026, 9, 27)},  # noqa: DTZ001 - naive on purpose
        {"retrieved_at": datetime(2026, 9, 27, tzinfo=timezone(timedelta(hours=2)))},
        {"sha256": "xyz"},
        {"path": "raw/letters/other/" + SHA + ".html"},
        {"unexpected": 1},
    ],
)
def test_strict_schema(bad: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        line(**bad)


def test_bad_line_in_text_names_line_number() -> None:
    with pytest.raises(ManifestError, match="line 2"):
        parse_manifest(serialise([line()]) + "{not json}\n")
