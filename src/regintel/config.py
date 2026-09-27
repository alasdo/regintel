"""Typed settings read from the environment."""

from __future__ import annotations

import os
from collections.abc import Mapping
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
