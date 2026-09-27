"""Shared pytest fixtures."""

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    """Directory holding small, readable input/expected-output files for golden tests."""
    return FIXTURES
