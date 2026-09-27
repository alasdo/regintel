"""The Hugging Face Dataset as a Store, with optimistic concurrency via parent_commit."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from huggingface_hub import CommitOperationAdd, HfApi
from huggingface_hub.errors import EntryNotFoundError, HfHubHTTPError

from regintel.store.base import ConcurrentWriteError

REPO_TYPE = "dataset"
_CONFLICT_STATUSES = frozenset({409, 412})


class HubStore:
    def __init__(self, repo_id: str, token: str | None, api: HfApi | None = None) -> None:
        self.repo_id = repo_id
        self._api = api if api is not None else HfApi(token=token)

    def head_revision(self) -> str:
        sha = self._api.repo_info(self.repo_id, repo_type=REPO_TYPE).sha
        if not sha:
            raise RuntimeError(f"{self.repo_id} has no head revision")
        return sha

    def read_bytes(self, path: str, revision: str) -> bytes | None:
        try:
            local = self._api.hf_hub_download(
                self.repo_id, path, repo_type=REPO_TYPE, revision=revision
            )
        except EntryNotFoundError:
            return None
        return Path(str(local)).read_bytes()

    def exists(self, path: str, revision: str) -> bool:
        return self._api.file_exists(self.repo_id, path, repo_type=REPO_TYPE, revision=revision)

    def list_paths(self, prefix: str, revision: str) -> list[str]:
        files = self._api.list_repo_files(self.repo_id, repo_type=REPO_TYPE, revision=revision)
        return sorted(f for f in files if f.startswith(prefix))

    def commit(self, additions: Mapping[str, bytes], message: str, parent_revision: str) -> str:
        operations = [
            CommitOperationAdd(path_in_repo=path, path_or_fileobj=data)
            for path, data in sorted(additions.items())
        ]
        try:
            info = self._api.create_commit(
                self.repo_id,
                operations,
                commit_message=message,
                repo_type=REPO_TYPE,
                parent_commit=parent_revision,
            )
        except HfHubHTTPError as exc:
            if exc.response.status_code in _CONFLICT_STATUSES:
                raise ConcurrentWriteError(
                    f"{self.repo_id} moved past {parent_revision}; nothing was written"
                ) from exc
            raise
        return str(info.oid)


def init_dataset(api: HfApi, repo_id: str) -> bool:
    """Create the public dataset repo if it is missing; True if it was created."""
    if api.repo_exists(repo_id, repo_type=REPO_TYPE):
        return False
    api.create_repo(repo_id, repo_type=REPO_TYPE, private=False)
    return True
