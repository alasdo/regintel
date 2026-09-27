"""PoliteClient: minimum interval, bounded retries, and stop-on-block."""

from datetime import UTC, datetime

import httpx
import pytest
import respx

from regintel.collect.http import BlockedError, FetchFailed, FetchPolicy, PoliteClient

URL = "https://www.fda.gov/letter"


class FakeTime:
    """Clock that advances only when the client sleeps."""

    def __init__(self) -> None:
        self.t = 1000.0
        self.sleeps: list[float] = []
        self.starts: list[float] = []

    def clock(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.sleeps.append(s)
        self.t += s


def make_client(ft: FakeTime, **policy: float) -> PoliteClient:
    def on_request(request: httpx.Request) -> None:
        ft.starts.append(ft.t)

    return PoliteClient(
        FetchPolicy(**policy),  # type: ignore[arg-type]
        "regintel-test",
        clock=ft.clock,
        sleep=ft.sleep,
        now=lambda: datetime(2026, 9, 27, tzinfo=UTC),
        on_request=on_request,
    )


@respx.mock
def test_min_interval_between_request_starts() -> None:
    ft = FakeTime()
    respx.get(URL).mock(side_effect=[httpx.Response(503), httpx.Response(200, text="a")])
    respx.get(URL + "2").mock(return_value=httpx.Response(200, text="b"))
    client = make_client(ft)
    client.get(URL)  # 503 then 200: two request starts
    client.get(URL + "2")
    gaps = [b - a for a, b in zip(ft.starts, ft.starts[1:], strict=False)]
    assert len(ft.starts) == 3
    assert all(g >= 30.0 for g in gaps), gaps


@respx.mock
def test_retries_then_succeeds() -> None:
    ft = FakeTime()
    respx.get(URL).mock(
        side_effect=[httpx.Response(503), httpx.Response(503), httpx.Response(200, text="ok")]
    )
    result = make_client(ft).get(URL)
    assert (result.status, result.body, result.attempts) == (200, b"ok", 3)
    assert ft.sleeps == [30.0, 60.0]
    assert result.retrieved_at == datetime(2026, 9, 27, tzinfo=UTC)


@respx.mock
def test_retries_on_timeout() -> None:
    ft = FakeTime()
    respx.get(URL).mock(side_effect=[httpx.ReadTimeout("slow"), httpx.Response(200, text="ok")])
    assert make_client(ft).get(URL).attempts == 2


@respx.mock
def test_honours_retry_after_capped() -> None:
    ft = FakeTime()
    respx.get(URL).mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "45"}),
            httpx.Response(429, headers={"Retry-After": "100000"}),
            httpx.Response(200),
        ]
    )
    make_client(ft).get(URL)
    assert ft.sleeps == [45.0, 300.0]


@respx.mock
def test_gives_up_after_max_attempts() -> None:
    ft = FakeTime()
    route = respx.get(URL).mock(return_value=httpx.Response(502))
    with pytest.raises(FetchFailed, match="502"):
        make_client(ft).get(URL)
    assert route.call_count == 4


@respx.mock
def test_403_raises_blocked_without_retry() -> None:
    ft = FakeTime()
    route = respx.get(URL).mock(return_value=httpx.Response(403, text="Access Denied"))
    with pytest.raises(BlockedError):
        make_client(ft).get(URL)
    assert route.call_count == 1


@respx.mock
def test_404_is_returned_not_raised() -> None:
    ft = FakeTime()
    respx.get(URL).mock(return_value=httpx.Response(404))
    assert make_client(ft).get(URL).status == 404


@respx.mock
def test_other_client_error_fails_without_retry() -> None:
    ft = FakeTime()
    route = respx.get(URL).mock(return_value=httpx.Response(410))
    with pytest.raises(FetchFailed, match="410"):
        make_client(ft).get(URL)
    assert route.call_count == 1


@respx.mock
def test_sends_honest_user_agent_and_params() -> None:
    ft = FakeTime()
    route = respx.get(URL).mock(return_value=httpx.Response(200))
    make_client(ft).get(URL, params={"start": 0, "length": 500})
    request = route.calls.last.request
    assert request.headers["User-Agent"] == "regintel-test"
    assert request.url.params["length"] == "500"


@respx.mock
def test_interval_holds_even_with_zero_retry_after() -> None:
    """Review #7: the wait, not the backoff, must keep retries 30 s apart."""
    ft = FakeTime()
    respx.get(URL).mock(
        side_effect=[httpx.Response(429, headers={"Retry-After": "0"}), httpx.Response(200)]
    )
    make_client(ft).get(URL)
    assert ft.starts[1] - ft.starts[0] >= 30.0


@respx.mock
def test_redirect_hops_are_spaced() -> None:
    """Review #6: each redirect hop is a request to fda.gov and waits its turn too."""
    ft = FakeTime()
    respx.get(URL).mock(return_value=httpx.Response(301, headers={"Location": URL + "-moved"}))
    respx.get(URL + "-moved").mock(return_value=httpx.Response(200, text="ok"))
    result = make_client(ft).get(URL)
    assert result.final_url == URL + "-moved"
    assert len(ft.starts) == 2
    assert ft.starts[1] - ft.starts[0] >= 30.0


@respx.mock
def test_redirect_loop_fails_cleanly() -> None:
    ft = FakeTime()
    respx.get(URL).mock(return_value=httpx.Response(302, headers={"Location": URL}))
    with pytest.raises(FetchFailed):
        make_client(ft).get(URL)
