"""guarded_commit is the only write path: append-only files grow, raw files never change."""

import re
from pathlib import Path

import pytest

from regintel.store.base import AppendOnlyViolation, ConcurrentWriteError, guarded_commit
from regintel.store.local import LocalStore

MANIFEST = "raw/manifest.jsonl"


@pytest.fixture
def store(tmp_path: Path) -> LocalStore:
    s = LocalStore(tmp_path / "ds")
    guarded_commit(
        s, {MANIFEST: b'{"a":1}\n', "raw/letters/x/abc.html": b"<html>1"}, "init", s.head_revision()
    )
    return s


def test_manifest_must_be_prefix_extension(store: LocalStore) -> None:
    head = store.head_revision()
    with pytest.raises(AppendOnlyViolation, match=re.escape(MANIFEST)):
        guarded_commit(store, {MANIFEST: b'{"a":2}\n{"b":1}\n'}, "rewrite", head)
    assert store.head_revision() == head
    assert store.read_bytes(MANIFEST, head) == b'{"a":1}\n'


def test_manifest_append_is_committed(store: LocalStore) -> None:
    head = store.head_revision()
    new = guarded_commit(store, {MANIFEST: b'{"a":1}\n{"b":1}\n'}, "append", head)
    assert new != head
    assert store.read_bytes(MANIFEST, new) == b'{"a":1}\n{"b":1}\n'


def test_existing_raw_path_not_overwritten(store: LocalStore) -> None:
    head = store.head_revision()
    with pytest.raises(AppendOnlyViolation, match=r"abc\.html"):
        guarded_commit(store, {"raw/letters/x/abc.html": b"<html>2"}, "overwrite", head)
    assert store.read_bytes("raw/letters/x/abc.html", head) == b"<html>1"


def test_identical_bytes_are_a_noop(store: LocalStore) -> None:
    head = store.head_revision()
    same = {"raw/letters/x/abc.html": b"<html>1", MANIFEST: b'{"a":1}\n'}
    assert guarded_commit(store, same, "noop", head) == head
    assert guarded_commit(store, {}, "empty", head) == head


@pytest.mark.parametrize(
    "path", ["derived/x.json", "bundle/a", "README.md", "raw/../derived/x", "/raw/x", "probe"]
)
def test_paths_outside_raw_and_probe_refused(store: LocalStore, path: str) -> None:
    with pytest.raises(AppendOnlyViolation):
        guarded_commit(store, {path: b"x"}, "bad", store.head_revision())


def test_probe_records_allowed_once(store: LocalStore) -> None:
    head = guarded_commit(store, {"probe/r1.json": b"{}"}, "probe", store.head_revision())
    with pytest.raises(AppendOnlyViolation):
        guarded_commit(store, {"probe/r1.json": b"{ }"}, "probe", head)


def test_stale_parent_is_a_concurrent_write(store: LocalStore) -> None:
    old = store.head_revision()
    guarded_commit(store, {"raw/letters/y/1.html": b"y"}, "other writer", old)
    with pytest.raises(ConcurrentWriteError):
        guarded_commit(store, {"raw/letters/z/1.html": b"z"}, "late", old)


def test_local_list_paths(store: LocalStore) -> None:
    head = store.head_revision()
    assert store.list_paths("raw/letters/", head) == ["raw/letters/x/abc.html"]
    assert store.list_paths("raw/", head) == ["raw/letters/x/abc.html", MANIFEST]
