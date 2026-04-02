from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path


LABELS_PATH = Path("eval/test_cases/classification_labels.jsonl")


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def safe_div(n: int, d: int) -> float:
    return n / d if d else 0.0


def main() -> None:
    rows = load_jsonl(LABELS_PATH)

    total = len(rows)
    overall_correct = 0

    type_totals = Counter()
    type_correct = Counter()

    severity_totals = Counter()
    severity_correct = Counter()

    confusion = defaultdict(Counter)

    for r in rows:
        expected_type = r["expected_type"]
        model_type = r["model_type"]
        expected_severity = r["expected_severity"]
        model_severity = r["model_severity"]

        if expected_type == model_type:
            type_correct[expected_type] += 1

        type_totals[expected_type] += 1
        confusion[expected_type][model_type] += 1

        if expected_type == model_type and expected_severity == model_severity:
            overall_correct += 1

        if expected_type == "substantive":
            severity_totals[expected_severity] += 1
            if expected_severity == model_severity:
                severity_correct[expected_severity] += 1

    print("Classification Evaluation Results")
    print("=" * 50)
    print(f"Labelled cases: {total}")
    print(f"Exact type+severity accuracy: {safe_div(overall_correct, total):.2%}")
    print()

    print("Accuracy by expected change type")
    for label in ["substantive", "editorial", "structural"]:
        print(
            f"  {label:12s} "
            f"{type_correct[label]}/{type_totals[label]} "
            f"({safe_div(type_correct[label], type_totals[label]):.2%})"
        )
    print()

    print("Severity accuracy for substantive changes")
    for sev in ["high", "medium", "low"]:
        print(
            f"  {sev:6s} "
            f"{severity_correct[sev]}/{severity_totals[sev]} "
            f"({safe_div(severity_correct[sev], severity_totals[sev]):.2%})"
        )
    print()

    print("Confusion summary (expected -> model)")
    for expected in ["substantive", "editorial", "structural"]:
        counts = confusion[expected]
        print(
            f"  {expected:12s} -> "
            f"substantive:{counts['substantive']} "
            f"editorial:{counts['editorial']} "
            f"structural:{counts['structural']}"
        )


if __name__ == "__main__":
    main()