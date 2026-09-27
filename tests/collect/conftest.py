"""Shared helpers for collector tests: a polite client that never really sleeps."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest

from regintel.collect.http import FetchPolicy, PoliteClient


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def clock(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.t += s

    def now(self) -> datetime:
        return datetime(2026, 9, 27, tzinfo=UTC) + timedelta(seconds=self.t)


@pytest.fixture
def make_client() -> Callable[[], PoliteClient]:
    def factory() -> PoliteClient:
        fc = FakeClock()
        return PoliteClient(
            FetchPolicy(), "regintel-test", clock=fc.clock, sleep=fc.sleep, now=fc.now
        )

    return factory
