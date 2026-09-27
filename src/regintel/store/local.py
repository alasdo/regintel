"""A directory that behaves like the Dataset: used by tests and `collect --no-push`."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from regintel.store.base import ConcurrentWriteError


class LocalStore:
    """Files under `root/tree`; the revision is a counter, so only the head is readable."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._tree = root / "tree"
        self._rev = root / "REVISION"

    def head_revision(self) -> str:
        return f"local-{int(self._rev.read_text()) if self._rev.exists() else 0}"

    def _check_head(self, revision: str) -> None:
        if revision != self.head_revision():
            raise ConcurrentWriteError(f"{revision} is not the head ({self.head_revision()})")

    def read_bytes(self, path: str, revision: str) -> bytes | None:
        self._check_head(revision)
        file = self._tree / path
        return file.read_bytes() if file.is_file() else None

    def exists(self, path: str, revision: str) -> bool:
        return self.read_bytes(path, revision) is not None

    def commit(self, additions: Mapping[str, bytes], message: str, parent_revision: str) -> str:
        self._check_head(parent_revision)
        for path, data in additions.items():
            file = self._tree / path
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(data)
        number = int(parent_revision.removeprefix("local-")) + 1
        self.root.mkdir(parents=True, exist_ok=True)
        self._rev.write_text(str(number))
        with (self.root / "commits.log").open("a", encoding="utf-8") as log:
            log.write(f"local-{number}\t{message}\n")
        return f"local-{number}"
