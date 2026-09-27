"""End-to-end collect runs against a fake fda.gov and a LocalStore (no network)."""

import gzip
import hashlib
import json
import random
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import pytest
import respx

from regintel.collect.http import FetchPolicy, PoliteClient
from regintel.collect.listing import LISTING_URL, ListingRow
from regintel.collect.manifest import (
    ManifestLine,
    SkipLine,
    parse_manifest,
    parse_skipped,
    serialise,
)
from regintel.collect.run import CollectSummary, collect, plan_fetches
from regintel.config import Settings
from regintel.letter_type import letter_type
from regintel.store.local import LocalStore

BASE = "/inspections-compliance-enforcement-and-criminal-investigations/warning-letters/"


@dataclass
class Letter:
    letter_id: str
    subject: str
    posted: str = "09/01/2026"
    office: str = "Center for Drug Evaluation and Research (CDER)"
    status: int = 200
    version: int = 1
    body: bytes | None = None

    def cells(self) -> list[str]:
        link = f'<a href="{BASE}{self.letter_id}">Firm {self.letter_id}</a>'
        issued = '<time datetime="2026-08-01T04:00:00Z">08/01/2026</time>\n'
        posted = f'<time datetime="2026-09-01T04:00:00Z">{self.posted}</time>\n'
        return [posted, issued, link, self.office, self.subject, "", "", ""]

    def html(self) -> bytes:
        if self.body is not None:
            return self.body
        return (
            f"<html><head><title>Firm {self.letter_id} | FDA</title></head><body>"
            f"<dl><dt>Issuing Office:</dt><dd>{self.office}</dd></dl>"
            f"<p>letter {self.letter_id} version {self.version}</p></body></html>"
        ).encode()


@dataclass
class FakeFda:
    letters: list[Letter]
    routes: dict[str, respx.Route] = field(default_factory=dict)

    def install(self, router: respx.MockRouter) -> None:
        router.get(LISTING_URL).mock(side_effect=self._listing)
        for letter in self.letters:
            self.routes[letter.letter_id] = router.get(
                f"https://www.fda.gov{BASE}{letter.letter_id}"
            ).mock(side_effect=lambda request, letter=letter: self._letter(letter))

    def _listing(self, request: httpx.Request) -> httpx.Response:
        start = int(request.url.params["start"])
        size = int(request.url.params["length"])
        data = [letter.cells() for letter in self.letters]
        page = {"recordsTotal": len(data), "data": data[start : start + size]}
        return httpx.Response(200, json=page)

    def _letter(self, letter: Letter) -> httpx.Response:
        return httpx.Response(letter.status, content=letter.html())

    def by_id(self, letter_id: str) -> Letter:
        return next(letter for letter in self.letters if letter.letter_id == letter_id)

    def calls(self, letter_id: str) -> int:
        return self.routes[letter_id].call_count


CGMP = "CGMP/Finished Pharmaceuticals/Adulterated"
API = "CGMP/Active Pharmaceutical Ingredient (API)/Adulterated"
COMPOUNDING = "Compounding Pharmacy/Adulterated Drug Products"
TELEHEALTH = "False &amp; Misleading Claims/Misbranded (Telehealth)"
DEVICE = "CGMP/QSR/Medical Devices/Adulterated"


def standard_site() -> FakeFda:
    return FakeFda(
        [
            Letter("alpha-1-09012026", CGMP, posted="09/03/2026"),
            Letter(
                "beta-2-08012026",
                API,
                posted="09/02/2026",
                office="Division of Pharmaceutical Quality Operations I",
            ),
            Letter("gamma-3-07012026", COMPOUNDING, posted="09/01/2026"),
            Letter("delta-4-07012026", TELEHEALTH),
            Letter("eps-5-07012026", DEVICE, office="Center for Devices and Radiological Health"),
        ]
    )


class Clock:
    def __init__(self, start: float = 0.0) -> None:
        self.t = start

    def clock(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.t += s

    def now(self) -> datetime:
        return datetime(2026, 9, 27, tzinfo=UTC) + timedelta(seconds=self.t)


@dataclass
class Env:
    tmp: Path
    store: LocalStore
    settings: Settings

    def client(self, start: float = 0.0) -> PoliteClient:
        c = Clock(start)
        return PoliteClient(FetchPolicy(), "regintel-test", clock=c.clock, sleep=c.sleep, now=c.now)

    def run(
        self, *, start: float = 0.0, store: LocalStore | None = None, **kw: int
    ) -> CollectSummary:
        summary = collect(self.settings, self.client(start), store or self.store, **kw)  # type: ignore[arg-type]
        assert_invariants(self.store)
        return summary

    def tree(self) -> dict[str, bytes]:
        root = self.store.root / "tree"
        return {
            p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()
        }

    def manifest(self) -> list[ManifestLine]:
        return parse_manifest(self.tree().get("raw/manifest.jsonl", b"").decode())


@pytest.fixture
def env(tmp_path: Path) -> Env:
    return Env(
        tmp_path,
        LocalStore(tmp_path / "ds"),
        Settings(cache_dir=tmp_path / "cache", hf_token=None),
    )


@pytest.fixture
def router() -> Iterator[respx.MockRouter]:
    with respx.mock(assert_all_called=False) as r:
        yield r


def assert_invariants(store: LocalStore) -> None:
    """Properties every run must leave behind (spec 0001: test_manifest_invariants)."""
    head = store.head_revision()
    text = (store.read_bytes("raw/manifest.jsonl", head) or b"").decode()
    lines = parse_manifest(text)  # also rejects duplicate (letter_id, sha256)
    assert serialise(lines) == text  # canonical: parse -> serialise round-trips byte for byte
    assert len({(m.letter_id, m.sha256) for m in lines}) == len(lines)
    for m in lines:
        body = store.read_bytes(m.path, head)
        assert body is not None, m.path
        assert hashlib.sha256(body).hexdigest() == m.sha256
        assert m.bytes == len(body)
        assert m.retrieved_at.utcoffset() == timedelta(0)
        assert m.letter_type == letter_type(m.listing.subject)
    parse_skipped((store.read_bytes("raw/skipped.jsonl", head) or b"").decode())


def snapshots(env: Env) -> list[str]:
    return sorted(p for p in env.tree() if p.startswith("raw/listing/"))


def test_first_run_fetches_only_in_scope(env: Env, router: respx.MockRouter) -> None:
    site = standard_site()
    site.install(router)
    summary = env.run()
    tree = env.tree()
    letters = sorted(p for p in tree if p.startswith("raw/letters/"))
    assert len(letters) == 3
    assert [m.letter_id for m in env.manifest()] == [
        "alpha-1-09012026",
        "beta-2-08012026",
        "gamma-3-07012026",
    ]
    assert site.calls("delta-4-07012026") == 0
    assert site.calls("eps-5-07012026") == 0
    assert len(snapshots(env)) == 1
    assert summary.in_scope_by_type == {"api": 1, "cgmp_finished": 1, "compounding": 1}
    assert (summary.listing_rows, summary.in_scope_rows, summary.new_manifest_lines) == (5, 3, 3)
    assert summary.blocked is False
    beta = next(m for m in env.manifest() if m.letter_id == "beta-2-08012026")
    assert beta.listing.issuing_office == "Division of Pharmaceutical Quality Operations I"


def test_snapshot_holds_all_rows_canonically(env: Env, router: respx.MockRouter) -> None:
    standard_site().install(router)
    env.run()
    (path,) = snapshots(env)
    raw = env.tree()[path]
    rows = [json.loads(x) for x in gzip.decompress(raw).decode().splitlines()]
    assert [r["letter_id"] for r in rows] == sorted(r["letter_id"] for r in rows)
    assert len(rows) == 5  # out-of-scope rows kept for audit
    sha8 = hashlib.sha256(gzip.decompress(raw)).hexdigest()[:8]
    assert path.endswith(f"-{sha8}.jsonl.gz")


def test_second_run_is_noop(env: Env, router: respx.MockRouter) -> None:
    site = standard_site()
    site.install(router)
    env.run()
    before = env.tree()
    head = env.store.head_revision()
    summary = env.run(start=10_000)
    assert summary.new_manifest_lines == 0
    assert summary.fetched == 0
    assert summary.commits == 0
    assert all(site.calls(letter.letter_id) <= 1 for letter in site.letters)
    assert env.store.head_revision() == head
    assert env.tree() == before


def test_repost_same_sha_adds_nothing(env: Env, router: respx.MockRouter) -> None:
    site = standard_site()
    site.install(router)
    env.run()
    site.by_id("alpha-1-09012026").posted = "09/20/2026"
    summary = env.run(start=10_000)
    assert site.calls("alpha-1-09012026") == 2
    assert (summary.unchanged_refetches, summary.new_manifest_lines) == (1, 0)
    assert len(snapshots(env)) == 2  # the new posted date is recorded
    env.run(start=20_000)
    assert site.calls("alpha-1-09012026") == 2  # no refetch loop


def test_repost_new_sha_appends(env: Env, router: respx.MockRouter) -> None:
    site = standard_site()
    site.install(router)
    env.run()
    old = env.tree()
    alpha = site.by_id("alpha-1-09012026")
    alpha.posted, alpha.version = "09/20/2026", 2
    summary = env.run(start=10_000)
    assert summary.new_manifest_lines == 1
    versions = [m for m in env.manifest() if m.letter_id == "alpha-1-09012026"]
    assert len(versions) == 2 and versions[0].sha256 != versions[1].sha256
    tree = env.tree()
    for path, data in old.items():
        if not path.endswith(".jsonl"):
            assert tree[path] == data  # nothing overwritten
    assert tree["raw/manifest.jsonl"].startswith(old["raw/manifest.jsonl"])
    env.run(start=20_000)
    assert site.calls("alpha-1-09012026") == 2


def test_404_recorded_and_not_retried(env: Env, router: respx.MockRouter) -> None:
    site = standard_site()
    site.by_id("gamma-3-07012026").status = 404
    site.install(router)
    summary = env.run()
    assert summary.skipped == {"http_404": 1}
    skipped = parse_skipped(env.tree()["raw/skipped.jsonl"].decode())
    assert [s.letter_id for s in skipped] == ["gamma-3-07012026"]
    env.run(start=10_000)
    assert site.calls("gamma-3-07012026") == 1


class FailingStore(LocalStore):
    """Fails the nth commit, like a network error mid-backfill."""

    def __init__(self, root: Path, fail_on: int) -> None:
        super().__init__(root)
        self.fail_on = fail_on
        self.count = 0

    def commit(self, additions: Mapping[str, bytes], message: str, parent_revision: str) -> str:
        self.count += 1
        if self.count == self.fail_on:
            raise OSError("network down")
        return super().commit(additions, message, parent_revision)


def test_crash_resume_pushes_pending_with_original_timestamp(
    env: Env, router: respx.MockRouter
) -> None:
    site = standard_site()
    site.install(router)
    failing = FailingStore(env.store.root, fail_on=2)
    with pytest.raises(OSError, match="network down"):
        collect(env.settings, env.client(), failing, batch_size=1)
    assert_invariants(env.store)  # the partial state is still valid
    pending = sorted((env.settings.cache_dir / "pending").rglob("record.json"))
    assert len(pending) == 1
    stranded = ManifestLine.model_validate_json(pending[0].read_text())
    assert stranded.letter_id == "beta-2-08012026"

    summary = env.run(start=50_000, batch_size=1)
    by_id = {m.letter_id: m for m in env.manifest()}
    assert by_id["beta-2-08012026"].retrieved_at == stranded.retrieved_at
    assert site.calls("beta-2-08012026") == 1  # pushed from cache, not refetched
    assert set(by_id) == {"alpha-1-09012026", "beta-2-08012026", "gamma-3-07012026"}
    assert summary.new_manifest_lines == 2
    assert not list((env.settings.cache_dir / "pending").rglob("record.json"))


def test_blocked_mid_run_pushes_progress(env: Env, router: respx.MockRouter) -> None:
    site = standard_site()
    site.by_id("beta-2-08012026").status = 403
    site.install(router)
    summary = env.run()
    assert summary.blocked is True
    assert [m.letter_id for m in env.manifest()] == ["alpha-1-09012026"]
    assert site.calls("gamma-3-07012026") == 0  # stopped at the block
    site.by_id("beta-2-08012026").status = 200
    env.run(start=10_000)  # unfetched new letters are simply planned again
    assert {m.letter_id for m in env.manifest()} == {
        "alpha-1-09012026",
        "beta-2-08012026",
        "gamma-3-07012026",
    }


def test_three_unexpected_pages_blocks(env: Env, router: respx.MockRouter) -> None:
    challenge = b"<html><title>Just a moment...</title></html>"
    site = FakeFda(
        [
            Letter(f"l{i}-{i}-01012026", CGMP, posted=f"09/0{i}/2026", body=challenge)
            for i in range(1, 6)
        ]
    )
    site.install(router)
    summary = env.run()
    assert summary.blocked is True
    assert summary.unexpected_pages == 3
    assert summary.fetched == 3
    assert env.manifest() == []


def test_max_fetches_limits_fetches(env: Env, router: respx.MockRouter) -> None:
    site = standard_site()
    site.install(router)
    summary = env.run(max_fetches=2)
    assert summary.fetched == 2
    assert len(snapshots(env)) == 1  # no reposts pending, so the listing is recorded
    summary = env.run(start=10_000)
    assert summary.new_manifest_lines == 1
    assert site.calls("gamma-3-07012026") == 1


def _row(letter_id: str, posted: date, subject: str = CGMP) -> ListingRow:
    return ListingRow(
        letter_id=letter_id,
        url=f"https://www.fda.gov{BASE}{letter_id}",
        posted_date=posted,
        issue_date=None,
        company="Firm",
        issuing_office="",
        subject=subject,
        response_letter_url=None,
        closeout_url=None,
        closeout_date=None,
    )


def test_plan_order_deterministic() -> None:
    rows = [_row(f"id-{i:02d}", date(2026, 1, 1 + i % 5)) for i in range(20)]
    expected = plan_fetches(rows, [], [], None)
    assert [r.posted_date for r in expected] == sorted((r.posted_date for r in rows), reverse=True)
    for seed in range(5):
        shuffled = rows[:]
        random.Random(seed).shuffle(shuffled)
        assert plan_fetches(shuffled, [], [], None) == expected


def test_plan_reposts_use_snapshot_not_manifest() -> None:
    a = _row("a", date(2026, 1, 1))
    known = [
        SkipLine(
            schema_version=1,
            letter_id="a",
            url=a.url,
            retrieved_at=datetime(2026, 1, 2, tzinfo=UTC),
            reason="http_404",
            run_id="r",
        )
    ]
    reposted = replace(a, posted_date=date(2026, 2, 1))
    assert plan_fetches([reposted], [], known, previous_snapshot=[a]) == [reposted]
    assert plan_fetches([a], [], known, previous_snapshot=[a]) == []
    assert plan_fetches([reposted], [], known, previous_snapshot=None) == []
    assert plan_fetches([a], [], [], previous_snapshot=[a]) == [a]  # unknown id is fetched


def test_blocked_mid_run_pushes_progress_and_exits_2(
    env: Env,
    router: respx.MockRouter,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from regintel import cli

    site = standard_site()
    site.by_id("beta-2-08012026").status = 403
    site.install(router)
    monkeypatch.setenv("REGINTEL_CACHE_DIR", str(env.settings.cache_dir))
    monkeypatch.setattr(cli, "_make_client", lambda settings, interval: env.client())
    assert cli.main(["collect", "--no-push"]) == 2
    local = LocalStore(env.settings.cache_dir / "local-dataset")
    manifest = parse_manifest(
        (local.read_bytes("raw/manifest.jsonl", local.head_revision()) or b"").decode()
    )
    assert [m.letter_id for m in manifest] == ["alpha-1-09012026"]
    assert json.loads(capsys.readouterr().out)["blocked"] is True
    assert_invariants(local)


CHALLENGE = b"<html><title>Just a moment...</title></html>"


def test_challenge_page_on_repost_does_not_hide_it(env: Env, router: respx.MockRouter) -> None:
    """Review #2: a repost that got a non-letter page must be retried, not snapshotted away."""
    site = standard_site()
    site.install(router)
    env.run()
    alpha = site.by_id("alpha-1-09012026")
    alpha.posted, alpha.version, alpha.body = "09/20/2026", 2, CHALLENGE
    summary = env.run(start=10_000)
    assert summary.unexpected_pages == 1
    alpha.body = None
    env.run(start=20_000)
    assert len([m for m in env.manifest() if m.letter_id == alpha.letter_id]) == 2


def test_repost_during_multi_run_backfill(env: Env, router: respx.MockRouter) -> None:
    """Review #3: a letter reposted before the first snapshot exists is still refetched."""
    site = standard_site()
    site.install(router)
    env.run(max_fetches=1)  # stores alpha; plan unfinished
    alpha = site.by_id("alpha-1-09012026")
    alpha.posted, alpha.version = "09/20/2026", 2
    env.run(start=10_000)
    assert len([m for m in env.manifest() if m.letter_id == alpha.letter_id]) == 2


def test_failing_new_letter_does_not_block_snapshots(env: Env, router: respx.MockRouter) -> None:
    """Review #4: one permanently failing new letter must not stop repost tracking."""
    site = standard_site()
    site.by_id("gamma-3-07012026").status = 410
    site.install(router)
    summary = env.run()
    assert summary.failed == 1
    assert len(snapshots(env)) == 1
    alpha = site.by_id("alpha-1-09012026")
    alpha.posted, alpha.version = "09/20/2026", 2
    env.run(start=10_000)
    assert len([m for m in env.manifest() if m.letter_id == alpha.letter_id]) == 2
    assert len(snapshots(env)) == 2


def test_failed_repost_defers_snapshot(env: Env, router: respx.MockRouter) -> None:
    site = standard_site()
    site.install(router)
    env.run()
    alpha = site.by_id("alpha-1-09012026")
    alpha.posted, alpha.version, alpha.status = "09/20/2026", 2, 410
    env.run(start=10_000)
    assert len(snapshots(env)) == 1  # repost unresolved: keep the old snapshot
    alpha.status = 200
    env.run(start=20_000)
    assert len([m for m in env.manifest() if m.letter_id == alpha.letter_id]) == 2
    assert len(snapshots(env)) == 2


def test_pending_pages_stay_with_their_store(env: Env, router: respx.MockRouter) -> None:
    """Review #5: a crashed dry run's pages must never be pushed to another store."""
    site = standard_site()
    site.install(router)
    dry = FailingStore(env.tmp / "dry-run", fail_on=1)
    with pytest.raises(OSError, match="network down"):
        collect(env.settings, env.client(), dry, batch_size=1)
    (record,) = (env.settings.cache_dir / "pending").rglob("record.json")
    stranded = ManifestLine.model_validate_json(record.read_text())

    env.run(start=10_000)  # the real store must not receive the dry run's page
    real = {m.letter_id: m for m in env.manifest()}
    assert real[stranded.letter_id].retrieved_at != stranded.retrieved_at
    assert record.exists()  # still waiting for its own store

    dry.fail_on = 0
    collect(env.settings, env.client(start=20_000), dry, batch_size=1)
    head = dry.head_revision()
    dry_lines = parse_manifest((dry.read_bytes("raw/manifest.jsonl", head) or b"").decode())
    by_id = {m.letter_id: m for m in dry_lines}
    assert by_id[stranded.letter_id].retrieved_at == stranded.retrieved_at
    assert not record.exists()


def test_manifest_invariants(env: Env, router: respx.MockRouter) -> None:
    """Spec 0001: invariants hold across new letters, a new version, a 404 and a no-op run.

    Every other run test also calls assert_invariants through Env.run.
    """
    site = standard_site()
    site.by_id("gamma-3-07012026").status = 404
    site.install(router)
    env.run()
    alpha = site.by_id("alpha-1-09012026")
    alpha.posted, alpha.version = "09/20/2026", 2
    env.run(start=10_000)
    env.run(start=20_000)
    lines = env.manifest()
    assert len(lines) == 3  # alpha v1, alpha v2, beta
    assert_invariants(env.store)
