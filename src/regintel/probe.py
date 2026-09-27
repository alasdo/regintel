"""Bot-block probe: can this machine (e.g. a GitHub runner) reach the listing and a letter?"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import time
from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict

from regintel.collect.http import BlockedError, FetchFailed, PoliteClient
from regintel.collect.listing import LISTING_PARAMS, LISTING_URL
from regintel.collect.page import looks_like_letter

log = logging.getLogger(__name__)

# A current drug CGMP letter (CGMP/Finished Pharmaceuticals/Adulterated, CDER, 2026-09-08).
DEFAULT_PROBE_URL = (
    "https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/"
    "warning-letters/kdcone-chatsworth-inc-733205-09082026"
)


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ProbeFetch(_Model):
    url: str
    status: int | None
    final_url: str | None = None
    bytes: int | None = None
    sha256: str | None = None
    attempts: int | None = None
    elapsed_s: float
    error: str | None = None


class ListingProbe(ProbeFetch):
    records_total: int | None = None


class LetterProbe(ProbeFetch):
    looks_like_letter: bool = False


class ProbeRecord(_Model):
    run_id: str
    retrieved_at: str
    github_run_id: str | None
    runner_os: str | None
    runner_name: str | None
    listing: ListingProbe
    letter: LetterProbe
    blocked: bool
    ok: bool


def _fetch(
    client: PoliteClient, url: str, params: Mapping[str, str | int] | None
) -> tuple[dict[str, object], bytes | None]:
    """Fetch once, never raising: returns the record fields and the body if there was one."""
    started = time.monotonic()
    fields: dict[str, object] = {"url": url, "status": None}
    body: bytes | None = None
    try:
        result = client.get(url, params=params)
    except BlockedError as exc:
        fields.update(status=403, error=str(exc))
    except FetchFailed as exc:
        fields.update(error=str(exc))
    else:
        body = result.body
        fields.update(
            status=result.status,
            final_url=result.final_url,
            bytes=len(body),
            sha256=hashlib.sha256(body).hexdigest(),
            attempts=result.attempts,
        )
    fields["elapsed_s"] = round(time.monotonic() - started, 3)
    return fields, body


def probe(client: PoliteClient, url: str, env: Mapping[str, str] | None = None) -> ProbeRecord:
    env = os.environ if env is None else env
    now = client.now()
    params: dict[str, str | int] = {**LISTING_PARAMS, "start": 0, "length": 10}

    listing, listing_body = _fetch(client, LISTING_URL, params)
    records_total = None
    if listing_body is not None:
        try:
            total = json.loads(listing_body).get("recordsTotal")
            records_total = total if isinstance(total, int) else None
        except (ValueError, AttributeError):
            records_total = None

    letter, letter_body = _fetch(client, url, None)
    is_letter = letter_body is not None and looks_like_letter(letter_body)

    blocked = 403 in (listing["status"], letter["status"])
    record = ProbeRecord(
        run_id=f"{now:%Y%m%dT%H%M%SZ}-{secrets.token_hex(4)}",
        retrieved_at=now.isoformat(),
        github_run_id=env.get("GITHUB_RUN_ID"),
        runner_os=env.get("RUNNER_OS"),
        runner_name=env.get("RUNNER_NAME"),
        listing=ListingProbe.model_validate({**listing, "records_total": records_total}),
        letter=LetterProbe.model_validate({**letter, "looks_like_letter": is_letter}),
        blocked=blocked,
        ok=not blocked and letter["status"] == 200 and is_letter,
    )
    log.info(
        "listing: status=%s bytes=%s sha256=%s records_total=%s",
        record.listing.status,
        record.listing.bytes,
        record.listing.sha256,
        record.listing.records_total,
    )
    log.info(
        "letter: status=%s bytes=%s sha256=%s looks_like_letter=%s",
        record.letter.status,
        record.letter.bytes,
        record.letter.sha256,
        record.letter.looks_like_letter,
    )
    return record
