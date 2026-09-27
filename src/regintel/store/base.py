"""Store protocol and the append-only guard every write goes through."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

APPENDABLE = frozenset({"raw/manifest.jsonl", "raw/skipped.jsonl"})
WRITABLE_PREFIXES = ("raw/", "probe/")


class AppendOnlyViolation(RuntimeError):
    """A write would change or remove data already in the store."""


class ConcurrentWriteError(RuntimeError):
    """Someone else committed since we read; nothing was written."""


class Store(Protocol):
    @property
    def identity(self) -> str:
        """Stable name of the destination, e.g. 'hub:alasdo/regintel-data'."""
        ...

    def head_revision(self) -> str: ...

    def read_bytes(self, path: str, revision: str) -> bytes | None: ...

    def exists(self, path: str, revision: str) -> bool: ...

    def list_paths(self, prefix: str, revision: str) -> list[str]: ...

    def commit(self, additions: Mapping[str, bytes], message: str, parent_revision: str) -> str: ...


def _check_path(path: str) -> None:
    parts = path.split("/")
    if (
        not path.startswith(WRITABLE_PREFIXES)
        or any(p in ("", ".", "..") for p in parts)
        or len(parts) < 2
    ):
        raise AppendOnlyViolation(f"writes are allowed only under raw/ and probe/: {path!r}")


def guarded_commit(
    store: Store, additions: Mapping[str, bytes], message: str, parent_revision: str
) -> str:
    """Commit additions unless any would overwrite data; return the resulting revision.

    Appendable files must extend their current bytes; every other path must be new.
    Additions identical to what is stored are dropped, so reruns commit nothing.
    """
    changed: dict[str, bytes] = {}
    for path, data in additions.items():
        _check_path(path)
        existing = store.read_bytes(path, parent_revision)
        if existing == data:
            continue
        if existing is not None and (path not in APPENDABLE or not data.startswith(existing)):
            raise AppendOnlyViolation(f"refusing to change existing {path}")
        changed[path] = data
    if not changed:
        return parent_revision
    return store.commit(changed, message, parent_revision)
