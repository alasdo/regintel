"""The autouse isolation in conftest.py: no owner .env, no credentials, no network."""

import os
from pathlib import Path

import httpx
import pytest

REPO = Path(__file__).resolve().parents[1]


def test_tests_do_not_run_from_the_repo() -> None:
    assert Path.cwd().resolve() != REPO
    assert not Path(".env").exists()
    assert "HF_TOKEN" not in os.environ


def test_real_network_is_refused_fast() -> None:
    with pytest.raises((RuntimeError, httpx.ConnectError), match="network"):
        httpx.get("https://www.fda.gov/", timeout=2)
