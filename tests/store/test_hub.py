"""HubStore maps the Store protocol onto huggingface_hub, with a fake HfApi (no network)."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx2
import pytest
from huggingface_hub.errors import (
    HfHubHTTPError,
    LocalEntryNotFoundError,
    RemoteEntryNotFoundError,
)

from regintel.store.base import ConcurrentWriteError
from regintel.store.hub import HubStore, init_dataset


def _http_error(cls: type[HfHubHTTPError], status: int) -> HfHubHTTPError:
    response = httpx2.Response(status, request=httpx2.Request("POST", "https://huggingface.co/x"))
    return cls("hub error", response=response)


@dataclass
class FakeApi:
    tmp: Path
    files: dict[str, bytes] = field(default_factory=dict)
    sha: str = "rev0"
    repos: set[str] = field(default_factory=set)
    created: list[dict[str, Any]] = field(default_factory=list)
    commits: list[dict[str, Any]] = field(default_factory=list)
    conflict: bool = False
    commit_error: int | None = None
    offline: bool = False

    def repo_info(self, repo_id: str, **kw: Any) -> Any:
        return type("Info", (), {"sha": self.sha})()

    def file_exists(self, repo_id: str, filename: str, **kw: Any) -> bool:
        return filename in self.files

    def hf_hub_download(self, repo_id: str, filename: str, **kw: Any) -> str:
        if self.offline:
            raise LocalEntryNotFoundError("connection issue or Hub downtime")
        if filename not in self.files:
            raise _http_error(RemoteEntryNotFoundError, 404)
        out = self.tmp / filename.replace("/", "_")
        out.write_bytes(self.files[filename])
        return str(out)

    def create_commit(self, repo_id: str, operations: Any, **kw: Any) -> Any:
        if self.conflict:
            self.sha = "rev-other"  # another writer got there first
            raise _http_error(HfHubHTTPError, 412)
        if self.commit_error is not None:
            raise _http_error(HfHubHTTPError, self.commit_error)
        self.commits.append({"ops": operations, **kw})
        for op in operations:
            self.files[op.path_in_repo] = op.path_or_fileobj
        self.sha = f"rev{len(self.commits)}"
        return type("CommitInfo", (), {"oid": self.sha})()

    def list_repo_files(self, repo_id: str, **kw: Any) -> list[str]:
        return list(self.files)

    def repo_exists(self, repo_id: str, **kw: Any) -> bool:
        return repo_id in self.repos

    def create_repo(self, repo_id: str, **kw: Any) -> None:
        self.created.append({"repo_id": repo_id, **kw})
        self.repos.add(repo_id)


def test_read_exists_and_commit_with_parent(tmp_path: Path) -> None:
    api = FakeApi(tmp_path, files={"raw/manifest.jsonl": b"a\n"})
    store = HubStore("alasdo/regintel-data", token=None, api=api)  # type: ignore[arg-type]
    head = store.head_revision()
    assert store.read_bytes("raw/manifest.jsonl", head) == b"a\n"
    assert store.read_bytes("raw/missing", head) is None
    assert store.exists("raw/manifest.jsonl", head)
    assert store.list_paths("raw/", head) == ["raw/manifest.jsonl"]
    assert store.list_paths("probe/", head) == []
    new = store.commit({"raw/letters/x/1.html": b"x"}, "msg", head)
    assert new == "rev1"
    assert api.commits[0]["parent_commit"] == "rev0"
    assert api.commits[0]["repo_type"] == "dataset"
    assert api.commits[0]["commit_message"] == "msg"


def test_parent_commit_conflict_raises_concurrent_write(tmp_path: Path) -> None:
    api = FakeApi(tmp_path, conflict=True)
    store = HubStore("alasdo/regintel-data", token=None, api=api)  # type: ignore[arg-type]
    with pytest.raises(ConcurrentWriteError):
        store.commit({"raw/letters/x/1.html": b"x"}, "msg", "rev0")


def test_init_dataset_idempotent_public(tmp_path: Path) -> None:
    api = FakeApi(tmp_path)
    assert init_dataset(api, "alasdo/regintel-data") is True  # type: ignore[arg-type]
    assert init_dataset(api, "alasdo/regintel-data") is False  # type: ignore[arg-type]
    assert api.created == [
        {"repo_id": "alasdo/regintel-data", "repo_type": "dataset", "private": False}
    ]


def test_hub_outage_is_not_read_as_missing_file(tmp_path: Path) -> None:
    """A network error must never look like 'no manifest': that would defeat the guard."""
    api = FakeApi(tmp_path, files={"raw/manifest.jsonl": b"a\n"}, offline=True)
    store = HubStore("alasdo/regintel-data", token=None, api=api)  # type: ignore[arg-type]
    with pytest.raises(LocalEntryNotFoundError):
        store.read_bytes("raw/manifest.jsonl", "rev0")


def test_any_commit_error_after_head_moved_is_concurrent(tmp_path: Path) -> None:
    api = FakeApi(tmp_path, commit_error=400, sha="rev9")  # someone else committed
    store = HubStore("alasdo/regintel-data", token=None, api=api)  # type: ignore[arg-type]
    with pytest.raises(ConcurrentWriteError):
        store.commit({"raw/letters/x/1.html": b"x"}, "msg", "rev0")


def test_commit_error_with_unmoved_head_propagates(tmp_path: Path) -> None:
    api = FakeApi(tmp_path, commit_error=500, sha="rev0")
    store = HubStore("alasdo/regintel-data", token=None, api=api)  # type: ignore[arg-type]
    with pytest.raises(HfHubHTTPError):
        store.commit({"raw/letters/x/1.html": b"x"}, "msg", "rev0")
