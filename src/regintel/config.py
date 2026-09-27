"""Typed settings read from the environment."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass, field
from pathlib import Path

from regintel import __version__

DEFAULT_DATASET = "alasdo/regintel-data"
USER_AGENT = f"regintel/{__version__} (+https://github.com/alasdo/regintel)"


@dataclass(frozen=True)
class Settings:
    dataset_repo: str = DEFAULT_DATASET
    hf_token: str | None = field(default=None, repr=False)
    cache_dir: Path = Path("data/cache")
    user_agent: str = USER_AGENT

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if env is None else env
        return cls(
            dataset_repo=env.get("REGINTEL_DATASET") or DEFAULT_DATASET,
            hf_token=env.get("HF_TOKEN") or None,
            cache_dir=Path(env.get("REGINTEL_CACHE_DIR") or "data/cache"),
        )


_DOTENV_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")


def _dotenv_value(raw: str) -> str:
    if raw[:1] in ("'", '"'):
        end = raw.find(raw[0], 1)
        if end != -1:
            return raw[1:end]
    return re.split(r"\s+#", raw, maxsplit=1)[0].strip()


def load_dotenv(
    path: Path = Path(".env"), environ: MutableMapping[str, str] | None = None
) -> list[str]:
    """Set KEY=VALUE pairs from a .env file; variables already set always win.

    Returns the names it set. Values are never logged.
    """
    environ = os.environ if environ is None else environ
    if not path.is_file():
        return []
    loaded = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _DOTENV_LINE.match(line)
        if not match or line.lstrip().startswith("#"):
            continue
        key, raw = match.groups()
        if key not in environ:
            environ[key] = _dotenv_value(raw)
            loaded.append(key)
    return loaded
