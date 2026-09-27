"""The probe workflow is manual-only, least-privilege, pinned, and injection-safe."""

import json
import re
from pathlib import Path
from typing import Any

import yaml

from regintel.letter_type import letter_type
from regintel.probe import DEFAULT_PROBE_URL

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "probe.yml"


def _load() -> dict[Any, Any]:
    data: dict[Any, Any] = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return data


def test_probe_workflow_shape(fixtures_dir: Path) -> None:
    wf = _load()
    triggers = wf[True]  # YAML 1.1 reads the bare key `on` as boolean True
    assert list(triggers) == ["workflow_dispatch"]
    assert wf["permissions"] == {"contents": "read"}

    steps = wf["jobs"]["probe"]["steps"]
    for step in steps:
        if "uses" in step:
            assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", step["uses"]), step["uses"]
        assert "${{" not in step.get("run", ""), f"expression interpolated in run: {step}"

    token_steps = [s for s in steps if "HF_TOKEN" in json.dumps(s)]
    assert len(token_steps) == 1
    assert token_steps[0]["env"]["HF_TOKEN"] == "${{ secrets.HF_TOKEN }}"
    assert "HF_TOKEN" not in json.dumps({k: v for k, v in wf.items() if k != "jobs"})
    assert "HF_TOKEN" not in json.dumps(wf["jobs"]["probe"].get("env", {}))
    assert token_steps[0]["env"]["PROBE_URL"] == "${{ inputs.url }}"


def test_default_url_is_an_in_scope_letter(fixtures_dir: Path) -> None:
    default = _load()[True]["workflow_dispatch"]["inputs"]["url"]["default"]
    assert default == DEFAULT_PROBE_URL
    expected = json.loads(
        (fixtures_dir / "collect" / "listing_page.expected.json").read_text(encoding="utf-8")
    )
    (row,) = [r for r in expected if r["url"] == default]
    assert letter_type(row["subject"]) == "cgmp_finished"


def test_workflow_never_calls_a_model() -> None:
    text = WORKFLOW.read_text(encoding="utf-8").lower()
    assert not re.search(r"ollama|classify|openai|anthropic", text)
