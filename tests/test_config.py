"""Settings come from the environment with safe defaults, and never expose the token."""

from pathlib import Path

from regintel.config import Settings


def test_defaults_without_env() -> None:
    s = Settings.from_env({})
    assert s.dataset_repo == "alasdo/regintel-data"
    assert s.hf_token is None
    assert s.cache_dir == Path("data/cache")
    assert s.user_agent.startswith("regintel/0.1.0 ")
    assert "github.com/alasdo/regintel" in s.user_agent


def test_env_overrides() -> None:
    s = Settings.from_env(
        {"REGINTEL_DATASET": "me/other", "HF_TOKEN": "hf_x", "REGINTEL_CACHE_DIR": "/tmp/c"}
    )
    assert (s.dataset_repo, s.hf_token, s.cache_dir) == ("me/other", "hf_x", Path("/tmp/c"))


def test_empty_token_is_none() -> None:
    assert Settings.from_env({"HF_TOKEN": ""}).hf_token is None


def test_repr_hides_token() -> None:
    assert "hf_secret_value" not in repr(Settings.from_env({"HF_TOKEN": "hf_secret_value"}))
