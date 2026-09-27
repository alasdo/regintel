"""Bot-block probe: one listing request and one letter page, recorded to probe/."""

import hashlib
import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import ClassVar

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


class FakeHfApi:
    """Stands in for huggingface_hub.HfApi on the real HubStore path (no network)."""

    instances: ClassVar[list["FakeHfApi"]] = []

    def __init__(self, token: str | None = None) -> None:
        self.token = token
        self.files: dict[str, bytes] = {}
        self.fail_commit = False
        FakeHfApi.instances.append(self)

    def repo_info(self, repo_id: str, **kw: object) -> object:
        return type("Info", (), {"sha": f"rev{len(self.files)}"})()

    def hf_hub_download(self, repo_id: str, filename: str, **kw: object) -> str:
        import httpx2
        from huggingface_hub.errors import RemoteEntryNotFoundError

        request = httpx2.Request("GET", "https://huggingface.co/x")
        raise RemoteEntryNotFoundError("404", response=httpx2.Response(404, request=request))

    def create_commit(self, repo_id: str, operations: list[object], **kw: object) -> object:
        if self.fail_commit:
            raise OSError("hub unreachable")
        for op in operations:
            self.files[op.path_in_repo] = op.path_or_fileobj  # type: ignore[attr-defined]
        return type("CommitInfo", (), {"oid": f"rev{len(self.files)}"})()


@pytest.fixture
def fake_hub(monkeypatch: pytest.MonkeyPatch) -> type[FakeHfApi]:
    FakeHfApi.instances = []
    monkeypatch.setattr("regintel.store.hub.HfApi", FakeHfApi)
    monkeypatch.setenv("HF_TOKEN", SENTINEL)
    monkeypatch.setattr(cli, "_make_client", lambda settings, interval: fast_client())
    return FakeHfApi


def test_probe_record_never_contains_token(
    router: respx.MockRouter,
    fake_hub: type[FakeHfApi],
    letter_html: bytes,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The token reaches HfApi (so the path is real) but no record, stdout or log."""
    router.get(LISTING_URL).mock(return_value=_listing())
    router.get(DEFAULT_PROBE_URL).mock(return_value=httpx.Response(200, content=letter_html))
    with caplog.at_level("DEBUG"):
        assert cli.main(["probe", "--push"]) == 0
    (api,) = fake_hub.instances
    assert api.token == SENTINEL
    ((path, data),) = api.files.items()
    assert path.startswith("probe/")
    assert SENTINEL.encode() not in data
    out = capsys.readouterr()
    assert SENTINEL not in out.out + out.err
    assert SENTINEL not in caplog.text


def test_probe_push_failure_exits_1_after_printing_record(
    router: respx.MockRouter,
    fake_hub: type[FakeHfApi],
    letter_html: bytes,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Review #13: a failed push is reported with an exit code, not a traceback."""
    router.get(LISTING_URL).mock(return_value=_listing())
    router.get(DEFAULT_PROBE_URL).mock(return_value=httpx.Response(200, content=letter_html))
    original = FakeHfApi.__init__

    def failing_init(self: FakeHfApi, token: str | None = None) -> None:
        original(self, token)
        self.fail_commit = True

    monkeypatch.setattr(FakeHfApi, "__init__", failing_init)
    assert cli.main(["probe", "--push"]) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is True  # the outcome was still printed


def test_probe_elapsed_excludes_politeness_wait(
    router: respx.MockRouter, letter_html: bytes
) -> None:
    """Review #16: elapsed_s measures fda.gov, not our own 30 s wait."""
    router.get(LISTING_URL).mock(return_value=_listing())
    router.get(DEFAULT_PROBE_URL).mock(return_value=httpx.Response(200, content=letter_html))
    client = PoliteClient(FetchPolicy(min_interval_s=0.5), "regintel-test")  # real 0.5 s wait
    record = probe(client, DEFAULT_PROBE_URL, env={})
    assert record.letter.elapsed_s is not None
    assert record.letter.elapsed_s < 0.4
