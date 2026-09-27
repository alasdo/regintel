"""Polite HTTP client: minimum interval between requests, bounded retries, stop on block."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx

log = logging.getLogger(__name__)

RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


@dataclass(frozen=True)
class FetchPolicy:
    min_interval_s: float = 30.0  # between request starts, retries included (robots.txt)
    max_attempts: int = 4
    backoff_base_s: float = 30.0  # 30, 60, 120; no jitter, so runs are reproducible
    retry_after_cap_s: float = 300.0
    timeout_s: float = 60.0


@dataclass(frozen=True)
class FetchResult:
    url: str
    final_url: str
    status: int
    body: bytes
    retrieved_at: datetime
    attempts: int


class BlockedError(RuntimeError):
    """The site refused us (403) or keeps serving non-letter pages; stop the run."""


class FetchFailed(RuntimeError):
    """Retries exhausted, or a non-retryable error status."""


def _utcnow() -> datetime:
    return datetime.now(UTC)


class PoliteClient:
    def __init__(
        self,
        policy: FetchPolicy,
        user_agent: str,
        *,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], datetime] = _utcnow,
        on_request: Callable[[httpx.Request], None] | None = None,
    ) -> None:
        self.policy = policy
        self._clock = clock
        self._sleep = sleep
        self._now = now
        self._last_start: float | None = None
        hooks = {"request": [on_request]} if on_request else {}
        self._http = httpx.Client(
            headers={"User-Agent": user_agent},
            timeout=policy.timeout_s,
            follow_redirects=True,
            transport=transport,
            event_hooks=hooks,
        )

    def now(self) -> datetime:
        """Current UTC time from the injected clock (tests control it)."""
        return self._now()

    def close(self) -> None:
        self._http.close()

    def _wait_turn(self) -> None:
        if self._last_start is not None:
            wait = self._last_start + self.policy.min_interval_s - self._clock()
            if wait > 0:
                self._sleep(wait)
        self._last_start = self._clock()

    def _retry_delay(self, attempt: int, response: httpx.Response | None) -> float:
        header = response.headers.get("Retry-After") if response is not None else None
        if header:
            seconds: float | None
            try:
                seconds = float(header)
            except ValueError:
                try:
                    seconds = (parsedate_to_datetime(header) - self._now()).total_seconds()
                except (TypeError, ValueError):
                    seconds = None
            if seconds is not None:
                return min(max(seconds, 0.0), self.policy.retry_after_cap_s)
        return float(self.policy.backoff_base_s * 2 ** (attempt - 1))

    def get(self, url: str, params: Mapping[str, str | int] | None = None) -> FetchResult:
        last_error = ""
        for attempt in range(1, self.policy.max_attempts + 1):
            self._wait_turn()
            response: httpx.Response | None = None
            try:
                response = self._http.get(url, params=params)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            else:
                status = response.status_code
                if status == 403:
                    raise BlockedError(f"403 from {url}")
                if status < 300 or status == 404:
                    return FetchResult(
                        url=url,
                        final_url=str(response.url),
                        status=status,
                        body=response.content,
                        retrieved_at=self._now(),
                        attempts=attempt,
                    )
                if status not in RETRY_STATUSES:
                    raise FetchFailed(f"HTTP {status} from {url}")
                last_error = f"HTTP {status}"
            if attempt < self.policy.max_attempts:
                delay = self._retry_delay(attempt, response)
                log.warning(
                    "%s on %s (attempt %d); retrying in %.0f s", last_error, url, attempt, delay
                )
                self._sleep(delay)
        raise FetchFailed(f"{last_error} from {url} after {self.policy.max_attempts} attempts")
