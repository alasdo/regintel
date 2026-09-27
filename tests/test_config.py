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


def test_load_dotenv_parses_and_never_overrides(tmp_path: Path) -> None:
    from regintel.config import load_dotenv

    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment\n"
        "\n"
        "HF_TOKEN=hf_from_file\n"
        "export REGINTEL_DATASET = 'me/quoted'\n"
        'REGINTEL_CACHE_DIR="/tmp/with space"  # trailing comment\n'
        "PLAIN=value # inline comment\n"
        "HASH_IN_QUOTES='a # b'\n"
        "ALREADY_SET=from_file\n"
        "not a variable line\n",
        encoding="utf-8",
    )
    environ = {"ALREADY_SET": "from_environment"}
    loaded = load_dotenv(env_file, environ)
    assert environ == {
        "ALREADY_SET": "from_environment",  # the environment (e.g. an Action secret) wins
        "HF_TOKEN": "hf_from_file",
        "REGINTEL_DATASET": "me/quoted",
        "REGINTEL_CACHE_DIR": "/tmp/with space",
        "PLAIN": "value",
        "HASH_IN_QUOTES": "a # b",
    }
    assert sorted(loaded) == sorted(set(environ) - {"ALREADY_SET"})


def test_load_dotenv_missing_file_is_a_noop(tmp_path: Path) -> None:
    from regintel.config import load_dotenv

    environ: dict[str, str] = {}
    assert load_dotenv(tmp_path / ".env", environ) == []
    assert environ == {}
