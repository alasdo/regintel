"""Manifest and skip-log records: one JSON object per line, strict schema, canonical form."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from typing import Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from regintel.collect.listing import ListingRow
from regintel.letter_type import LetterType

SHA256 = r"^[0-9a-f]{64}$"


class ManifestError(ValueError):
    """The manifest text is not a valid sequence of records."""


class _Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _require_utc(value: datetime) -> datetime:
    if value.utcoffset() != timedelta(0):
        raise ValueError("timestamps must be timezone-aware UTC")
    return value


class ListingFields(_Record):
    posted_date: date
    issue_date: date | None
    company: str
    issuing_office: str
    subject: str
    response_letter_url: str | None
    closeout_url: str | None
    closeout_date: date | None

    @classmethod
    def from_row(cls, row: ListingRow) -> ListingFields:
        return cls(
            posted_date=row.posted_date,
            issue_date=row.issue_date,
            company=row.company,
            issuing_office=row.issuing_office,
            subject=row.subject,
            response_letter_url=row.response_letter_url,
            closeout_url=row.closeout_url,
            closeout_date=row.closeout_date,
        )


class ManifestLine(_Record):
    schema_version: Literal[1]
    letter_id: str = Field(min_length=1)
    url: str
    retrieved_at: datetime
    sha256: str = Field(pattern=SHA256)
    bytes: int = Field(ge=0)
    http_status: int
    path: str
    listing: ListingFields
    letter_type: LetterType
    rules_version: int
    rules_sha256: str = Field(pattern=SHA256)
    run_id: str
    collector_version: str

    _utc = field_validator("retrieved_at")(_require_utc)

    @model_validator(mode="after")
    def _path_matches(self) -> ManifestLine:
        if self.path != letter_path(self.letter_id, self.sha256):
            raise ValueError(f"path {self.path!r} does not match letter_id and sha256")
        return self


class SkipLine(_Record):
    schema_version: Literal[1]
    letter_id: str = Field(min_length=1)
    url: str
    retrieved_at: datetime
    reason: Literal["http_404"]
    run_id: str

    _utc = field_validator("retrieved_at")(_require_utc)


def letter_path(letter_id: str, sha256: str) -> str:
    return f"raw/letters/{letter_id}/{sha256}.html"


R = TypeVar("R", bound=_Record)


def _parse(text: str, model: type[R]) -> list[R]:
    records: list[R] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        try:
            records.append(model.model_validate(json.loads(raw)))
        except (ValueError, ValidationError) as exc:
            raise ManifestError(f"{model.__name__} line {number} is invalid: {exc}") from exc
    return records


def parse_manifest(text: str) -> list[ManifestLine]:
    lines = _parse(text, ManifestLine)
    seen: set[tuple[str, str]] = set()
    for line in lines:
        key = (line.letter_id, line.sha256)
        if key in seen:
            raise ManifestError(f"duplicate manifest entry for {key}")
        seen.add(key)
    return lines


def parse_skipped(text: str) -> list[SkipLine]:
    return _parse(text, SkipLine)


def serialise(records: Sequence[BaseModel]) -> str:
    """Canonical JSONL: sorted keys, UTF-8, one trailing newline per record."""
    return "".join(
        json.dumps(r.model_dump(mode="json"), sort_keys=True, ensure_ascii=False) + "\n"
        for r in records
    )
