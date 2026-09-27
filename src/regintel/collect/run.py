"""One collect run: listing -> in-scope plan -> polite fetches -> guarded, batched commits."""

from __future__ import annotations

import dataclasses
import gzip
import hashlib
import json
import logging
import re
import secrets
import shutil
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from regintel import __version__
from regintel.collect.http import BlockedError, FetchFailed, PoliteClient
from regintel.collect.listing import ListingRow, fetch_listing
from regintel.collect.manifest import (
    ListingFields,
    ManifestLine,
    SkipLine,
    letter_path,
    parse_manifest,
    parse_skipped,
    serialise,
)
from regintel.collect.page import looks_like_letter
from regintel.config import Settings
from regintel.letter_type import RULES_VERSION, letter_type, rules_sha256
from regintel.store.base import Store, guarded_commit

log = logging.getLogger(__name__)

MANIFEST = "raw/manifest.jsonl"
SKIPPED = "raw/skipped.jsonl"
SNAPSHOT_DIR = "raw/listing/"
MAX_CONSECUTIVE_UNEXPECTED = 3
_DRUG_LIKE = re.compile(r"CGMP|Pharm", re.IGNORECASE)


@dataclass(frozen=True)
class CollectSummary:
    run_id: str
    rules_version: int
    listing_rows: int
    duplicate_rows_dropped: int
    in_scope_rows: int
    in_scope_by_type: dict[str, int]
    out_of_scope_drug_like: int  # out-of-scope rows mentioning CGMP/Pharm: review new phrasings
    planned: int
    fetched: int
    failed: int
    new_manifest_lines: int
    unchanged_refetches: int
    skipped: dict[str, int]
    unexpected_pages: int
    commits: int
    blocked: bool
    snapshot_written: bool
    unresolved_reposts: list[str]  # reposts holding the snapshot back: investigate if persistent
    dataset_revision_before: str
    dataset_revision_after: str


def plan_fetches(
    in_scope: Sequence[ListingRow],
    manifest: Sequence[ManifestLine],
    skipped: Sequence[SkipLine],
    previous_snapshot: Sequence[ListingRow] | None,
) -> list[ListingRow]:
    """Rows to fetch: unknown ids, plus known ids FDA reposted since we last saw them.

    "Last seen" is the posted date in the latest snapshot, or, for ids the snapshot lacks
    (e.g. mid-backfill), the posted date on the newest manifest line for that id.
    Comparing against the snapshot means a same-hash refetch is not repeated every run.
    Newest posted first, ties by letter_id.
    """
    known = {m.letter_id for m in manifest} | {s.letter_id for s in skipped}
    last_seen: dict[str, date] = {}
    for line in sorted(manifest, key=lambda m: m.retrieved_at):
        last_seen[line.letter_id] = line.listing.posted_date
    last_seen.update({r.letter_id: r.posted_date for r in previous_snapshot or ()})
    plan = [
        row
        for row in in_scope
        if row.letter_id not in known
        or (row.letter_id in last_seen and last_seen[row.letter_id] != row.posted_date)
    ]
    return sorted(plan, key=lambda r: (-r.posted_date.toordinal(), r.letter_id))


def snapshot_bytes(rows: Sequence[ListingRow]) -> bytes:
    """Canonical, uncompressed snapshot content: rows sorted by id, sorted keys."""
    ordered = sorted(rows, key=lambda r: r.letter_id)
    return "".join(
        json.dumps(dataclasses.asdict(r), sort_keys=True, default=date.isoformat) + "\n"
        for r in ordered
    ).encode()


def _parse_snapshot(raw: bytes) -> list[ListingRow]:
    rows = []
    for line in gzip.decompress(raw).decode().splitlines():
        record = json.loads(line)
        for key in ("posted_date", "issue_date", "closeout_date"):
            if record[key] is not None:
                record[key] = date.fromisoformat(record[key])
        rows.append(ListingRow(**record))
    return rows


class _Pending:
    """Fetched-but-unpushed pages on local disk, so a crash loses nothing."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def _dir(self, line: ManifestLine) -> Path:
        return self.root / line.letter_id / line.sha256

    def save(self, line: ManifestLine, body: bytes) -> None:
        folder = self._dir(line)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "page.html").write_bytes(body)
        (folder / "record.json").write_text(line.model_dump_json(), encoding="utf-8")

    def load(self) -> list[tuple[ManifestLine, bytes]]:
        records = []
        for record in sorted(self.root.glob("*/*/record.json")):
            line = ManifestLine.model_validate_json(record.read_text(encoding="utf-8"))
            body = (record.parent / "page.html").read_bytes()
            if hashlib.sha256(body).hexdigest() != line.sha256:
                raise RuntimeError(f"pending page {record.parent} does not match its record")
            records.append((line, body))
        return records

    def remove(self, line: ManifestLine) -> None:
        shutil.rmtree(self._dir(line), ignore_errors=True)


class _Writer:
    """Holds the dataset state for this run and commits batches through the guard."""

    def __init__(self, store: Store, run_id: str) -> None:
        self.store = store
        self.run_id = run_id
        self.head = store.head_revision()
        self.manifest_bytes = store.read_bytes(MANIFEST, self.head) or b""
        self.skipped_bytes = store.read_bytes(SKIPPED, self.head) or b""
        self.manifest = parse_manifest(self.manifest_bytes.decode())
        self.skipped = parse_skipped(self.skipped_bytes.decode())
        self.versions = {(m.letter_id, m.sha256) for m in self.manifest}
        self.commits = 0
        self.new_lines = 0

    def latest_snapshot(self) -> tuple[str, list[ListingRow]] | None:
        paths = self.store.list_paths(SNAPSHOT_DIR, self.head)
        if not paths:
            return None
        latest = max(paths)
        raw = self.store.read_bytes(latest, self.head)
        if raw is None:
            raise RuntimeError(f"snapshot {latest} vanished")
        return latest, _parse_snapshot(raw)

    def flush(
        self,
        pages: Sequence[tuple[ManifestLine, bytes]],
        skips: Sequence[SkipLine],
        extra: dict[str, bytes] | None = None,
    ) -> None:
        if not pages and not skips and not extra:
            return
        lines = [line for line, _ in pages]
        additions = {line.path: body for line, body in pages}
        if lines:
            additions[MANIFEST] = self.manifest_bytes + serialise(lines).encode()
        if skips:
            additions[SKIPPED] = self.skipped_bytes + serialise(skips).encode()
        additions.update(extra or {})
        parts = [f"{len(lines)} letters", f"{len(skips)} skips"]
        if extra:
            parts.append("listing snapshot")
        message = f"collect {self.run_id}: " + ", ".join(parts)
        revision = guarded_commit(self.store, additions, message, self.head)
        if revision != self.head:
            self.commits += 1
            self.head = revision
        self.manifest_bytes = additions.get(MANIFEST, self.manifest_bytes)
        self.skipped_bytes = additions.get(SKIPPED, self.skipped_bytes)
        self.manifest.extend(lines)
        self.skipped.extend(skips)
        self.versions |= {(m.letter_id, m.sha256) for m in lines}
        self.new_lines += len(lines)


def _new_run_id(client: PoliteClient) -> str:
    return f"{client.now():%Y%m%dT%H%M%SZ}-{secrets.token_hex(4)}"


def collect(
    settings: Settings,
    client: PoliteClient,
    store: Store,
    *,
    max_fetches: int | None = None,
    batch_size: int = 50,
) -> CollectSummary:
    run_id = _new_run_id(client)
    writer = _Writer(store, run_id)
    revision_before = writer.head
    # Pending pages belong to one destination: a dry run's pages never reach the Hub.
    store_key = hashlib.sha256(store.identity.encode()).hexdigest()[:12]
    pending = _Pending(settings.cache_dir / "pending" / store_key)

    # 1. Push anything a previous run fetched but could not commit.
    stranded = []
    for line, body in pending.load():
        if (line.letter_id, line.sha256) in writer.versions:
            pending.remove(line)
        else:
            stranded.append((line, body))
    if stranded:
        log.info("pushing %d pages left pending by an earlier run", len(stranded))
        writer.flush(stranded, [])
        for line, _ in stranded:
            pending.remove(line)

    # 2. Listing and plan.
    listing, dropped = fetch_listing(client)
    in_scope = [r for r in listing if letter_type(r.subject)]
    drug_like = sorted(
        {r.subject for r in listing if not letter_type(r.subject) and _DRUG_LIKE.search(r.subject)}
    )
    previous = writer.latest_snapshot()
    plan = plan_fetches(in_scope, writer.manifest, writer.skipped, previous and previous[1])
    known_ids = {m.letter_id for m in writer.manifest} | {s.letter_id for s in writer.skipped}
    reposts = {r.letter_id for r in plan if r.letter_id in known_ids}
    resolved: set[str] = set()  # reposts that got a definitive answer (letter page or 404)
    todo = plan if max_fetches is None else plan[:max_fetches]
    log.info("listing %d rows, %d in scope, %d to fetch", len(listing), len(in_scope), len(todo))

    # 3. Fetch politely, committing in batches.
    batch: list[tuple[ManifestLine, bytes]] = []
    skips: list[SkipLine] = []
    fetched = failed = unexpected = consecutive = unchanged = 0
    skip_counts: Counter[str] = Counter()
    blocked = False
    for row in todo:
        try:
            result = client.get(row.url)
        except BlockedError as exc:
            log.error("blocked: %s", exc)
            blocked = True
            break
        except FetchFailed as exc:
            log.warning("giving up on %s this run: %s", row.letter_id, exc)
            failed += 1
            continue
        fetched += 1
        if result.status == 404:
            skips.append(
                SkipLine(
                    schema_version=1,
                    letter_id=row.letter_id,
                    url=row.url,
                    retrieved_at=result.retrieved_at,
                    reason="http_404",
                    run_id=run_id,
                )
            )
            skip_counts["http_404"] += 1
            resolved.add(row.letter_id)
        elif not looks_like_letter(result.body):
            unexpected += 1
            consecutive += 1
            log.warning("%s did not look like a letter page; not stored", row.url)
            if consecutive >= MAX_CONSECUTIVE_UNEXPECTED:
                log.error("%d unexpected pages in a row; treating as blocked", consecutive)
                blocked = True
                break
            continue
        else:
            resolved.add(row.letter_id)
            sha = hashlib.sha256(result.body).hexdigest()
            if (row.letter_id, sha) in writer.versions:
                unchanged += 1
            else:
                line = ManifestLine(
                    schema_version=1,
                    letter_id=row.letter_id,
                    url=row.url,
                    retrieved_at=result.retrieved_at,
                    sha256=sha,
                    bytes=len(result.body),
                    http_status=result.status,
                    path=letter_path(row.letter_id, sha),
                    listing=ListingFields.from_row(row),
                    letter_type=letter_type(row.subject),  # type: ignore[arg-type]
                    rules_version=RULES_VERSION,
                    rules_sha256=rules_sha256(),
                    run_id=run_id,
                    collector_version=__version__,
                )
                pending.save(line, result.body)
                batch.append((line, result.body))
        consecutive = 0
        if len(batch) + len(skips) >= batch_size:
            writer.flush(batch, skips)
            for line, _ in batch:
                pending.remove(line)
            batch, skips = [], []

    # 4. Final batch, plus a listing snapshot. A snapshot marks reposts as seen, so it is
    #    written only when every repost got a definitive answer; unfetched *new* letters
    #    need no gate, because they stay unknown and are planned again next run.
    extra: dict[str, bytes] = {}
    complete = reposts <= resolved
    unresolved = sorted(reposts - resolved)
    if unresolved:
        log.warning(
            "listing snapshot held back by %d unresolved reposts: %s", len(unresolved), unresolved
        )
    content = snapshot_bytes(listing)
    previous_content = snapshot_bytes(previous[1]) if previous else None
    if complete and content != previous_content:
        sha8 = hashlib.sha256(content).hexdigest()[:8]
        name = f"{SNAPSHOT_DIR}{client.now():%Y%m%dT%H%M%SZ}-{sha8}.jsonl.gz"
        extra[name] = gzip.compress(content, mtime=0)
    writer.flush(batch, skips, extra)
    for line, _ in batch:
        pending.remove(line)

    drug_like_set = set(drug_like)
    seen_before = {r.subject for r in previous[1]} if previous else set()
    for subject in drug_like:
        if subject not in seen_before:
            log.info("new out-of-scope subject mentioning CGMP/Pharm: %r", subject)
    return CollectSummary(
        run_id=run_id,
        rules_version=RULES_VERSION,
        listing_rows=len(listing),
        duplicate_rows_dropped=dropped,
        in_scope_rows=len(in_scope),
        in_scope_by_type=dict(
            sorted(Counter(str(letter_type(r.subject)) for r in in_scope).items())
        ),
        out_of_scope_drug_like=sum(1 for r in listing if r.subject in drug_like_set),
        planned=len(plan),
        fetched=fetched,
        failed=failed,
        new_manifest_lines=writer.new_lines,
        unchanged_refetches=unchanged,
        skipped=dict(skip_counts),
        unexpected_pages=unexpected,
        commits=writer.commits,
        blocked=blocked,
        snapshot_written=bool(extra),
        unresolved_reposts=unresolved,
        dataset_revision_before=revision_before,
        dataset_revision_after=writer.head,
    )
