"""Bot-block probe: one listing request and one letter page, recorded to probe/."""

import hashlib
import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
import respx

from regintel import cli
from regintel.collect.http import FetchPolicy, PoliteClient
from regintel.collect.listing import LISTING_URL
from regintel.probe import DEFAULT_PROBE_URL, probe
from regintel.store.local import LocalStore

SENTINEL = "hf_test_sentinel_do_not_leak"


def fast_client() -> PoliteClient:
    t = {"now": 0.0}

    def sleep(s: float) -> None:
        t["now"] += s

    return PoliteClient(
        FetchPolicy(),
        "regintel-test",
        clock=lambda: t["now"],
        sleep=sleep,
        now=lambda: datetime(2026, 9, 27, tzinfo=UTC) + timedelta(seconds=t["now"]),
    )


@pytest.fixture
def letter_html(fixtures_dir: Path) -> bytes:
    return (fixtures_dir / "collect" / "letter_cgmp.html").read_bytes()


@pytest.fixture
def router() -> Iterator[respx.MockRouter]:
    with respx.mock(assert_all_called=False) as r:
        yield r


def _listing() -> httpx.Response:
    return httpx.Response(200, json={"recordsTotal": 3701, "data": []})


def test_probe_ok_record(router: respx.MockRouter, letter_html: bytes) -> None:
    listing = router.get(LISTING_URL).mock(return_value=_listing())
    router.get(DEFAULT_PROBE_URL).mock(return_value=httpx.Response(200, content=letter_html))
    record = probe(
        fast_client(), DEFAULT_PROBE_URL, env={"GITHUB_RUN_ID": "42", "RUNNER_OS": "Linux"}
    )
    assert listing.calls.last.request.url.params["length"] == "10"
    assert record.blocked is False
    assert record.ok is True
    assert record.github_run_id == "42"
    assert record.listing.status == 200 and record.listing.records_total == 3701
    assert record.letter.status == 200
    assert record.letter.looks_like_letter is True
    assert record.letter.sha256 == hashlib.sha256(letter_html).hexdigest()
    assert record.letter.bytes == len(letter_html)


def test_probe_challenge_page_is_not_ok(router: respx.MockRouter) -> None:
    router.get(LISTING_URL).mock(return_value=_listing())
    router.get(DEFAULT_PROBE_URL).mock(
        return_value=httpx.Response(200, content=b"<html><title>Just a moment</title></html>")
    )
    record = probe(fast_client(), DEFAULT_PROBE_URL, env={})
    assert (record.ok, record.blocked, record.letter.looks_like_letter) == (False, False, False)


def _run_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[int, LocalStore]:
    store = LocalStore(tmp_path / "ds")
    monkeypatch.setenv("HF_TOKEN", SENTINEL)
    monkeypatch.setattr(cli, "_make_client", lambda settings, interval: fast_client())
    monkeypatch.setattr(cli, "_make_store", lambda settings, push: store)
    return cli.main(["probe", "--push"]), store


def test_probe_blocked_exits_2_and_still_pushes(
    router: respx.MockRouter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    router.get(LISTING_URL).mock(return_value=_listing())
    router.get(DEFAULT_PROBE_URL).mock(return_value=httpx.Response(403, text="Access Denied"))
    code, store = _run_cli(tmp_path, monkeypatch)
    assert code == 2
    head = store.head_revision()
    (path,) = store.list_paths("probe/", head)
    stored = json.loads(store.read_bytes(path, head) or b"")
    assert stored["blocked"] is True
    assert stored["letter"]["status"] == 403
    assert path == f"probe/{stored['run_id']}.json"


def test_probe_record_never_contains_token(
    router: respx.MockRouter,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    letter_html: bytes,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    router.get(LISTING_URL).mock(return_value=_listing())
    router.get(DEFAULT_PROBE_URL).mock(return_value=httpx.Response(200, content=letter_html))
    with caplog.at_level("DEBUG"):
        code, store = _run_cli(tmp_path, monkeypatch)
    assert code == 0
    head = store.head_revision()
    (path,) = store.list_paths("probe/", head)
    assert SENTINEL.encode() not in (store.read_bytes(path, head) or b"")
    out = capsys.readouterr()
    assert SENTINEL not in out.out + out.err
    assert SENTINEL not in caplog.text
