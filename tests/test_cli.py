"""CLI guards that must hold before any request is made."""

from pathlib import Path

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


def test_cli_reads_token_from_dotenv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Bug: `uv run regintel store init` ignored a filled-in .env."""
    import regintel.store.hub as hub

    seen: dict[str, object] = {}

    class FakeApi:
        def __init__(self, token: str | None = None) -> None:
            seen["token"] = token

    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("REGINTEL_DATASET", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("HF_TOKEN=hf_dotenv\n", encoding="utf-8")
    monkeypatch.setattr("huggingface_hub.HfApi", FakeApi)
    monkeypatch.setattr(hub, "init_dataset", lambda api, repo: False)
    assert cli.main(["store", "init"]) == 0
    assert seen["token"] == "hf_dotenv"
    assert "exists alasdo/regintel-data" in capsys.readouterr().out


def test_environment_beats_dotenv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import os

    monkeypatch.setenv("HF_TOKEN", "hf_from_action_secret")
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("HF_TOKEN=hf_dotenv\n", encoding="utf-8")
    monkeypatch.setattr(cli, "cmd_store_init", lambda args: 0)
    cli.main(["store", "init"])
    assert os.environ["HF_TOKEN"] == "hf_from_action_secret"
