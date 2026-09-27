"""CLI guards that must hold before any request is made."""

import pytest
import respx

from regintel import cli


@respx.mock(assert_all_mocked=True)
def test_min_interval_below_30_refused(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    monkeypatch.setenv("REGINTEL_CACHE_DIR", str(tmp_path))
    assert cli.main(["collect", "--no-push", "--min-interval", "29"]) == 1
    assert len(respx.calls) == 0


def test_push_without_token_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HF_TOKEN", raising=False)
    with pytest.raises(SystemExit, match="HF_TOKEN"):
        cli.main(["collect"])


def test_store_init_without_token_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HF_TOKEN", raising=False)
    assert cli.main(["store", "init"]) == 1


@pytest.mark.parametrize(
    "args",
    [["collect", "--max-fetches", "-1"], ["collect", "--batch-size", "0"]],
)
def test_bad_numbers_rejected(args: list[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(args)
    assert exc.value.code == 2  # argparse usage error
