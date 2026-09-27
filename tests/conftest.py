"""Shared pytest fixtures, and isolation every test gets automatically."""

import socket
from collections.abc import Iterator
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
REGINTEL_ENV = ("HF_TOKEN", "REGINTEL_DATASET", "REGINTEL_CACHE_DIR")


@pytest.fixture
def fixtures_dir() -> Path:
    """Directory holding small, readable input/expected-output files for golden tests."""
    return FIXTURES


@pytest.fixture(autouse=True)
def _isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """No test may see the owner's .env or credentials, or reach the network.

    Tests run from an empty temporary directory (so the CLI finds no .env) with the
    regintel variables cleared, and opening a real socket fails immediately instead
    of silently fetching from fda.gov or writing to the Hub.
    """
    monkeypatch.chdir(tmp_path)
    for name in REGINTEL_ENV:
        monkeypatch.delenv(name, raising=False)

    def refuse(*args: object, **kwargs: object) -> None:
        raise RuntimeError(f"tests must not open network connections: {args!r}")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    yield
