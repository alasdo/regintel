"""The subject-line rule table decides scope (collector) and letter type (parser)."""

import csv
from pathlib import Path

import pytest

from regintel.letter_type import RULES_VERSION, letter_type, rules_sha256

# Update only together with a RULES_VERSION bump and a reviewed golden-table diff.
PINNED_RULES_SHA256 = "08da208f31a5dbfe7dcf3d828e95eeda64f4f0ae3f5fc620b8e67e8e037c4149"

# Spot check from spec 0001: 8 domestic drug CGMP letters fetched on 2026-09-27.
SPOT_CHECK = [
    (
        "Diamond Chemical Co., Inc.",
        "Division of Pharmaceutical Quality Operations I",
        "CGMP/Finished Pharmaceuticals/Adulterated",
    ),
    (
        "Clean Solutions LLC",
        "Division of Pharmaceutical Quality Operations I",
        "CGMP/Finished Pharmaceuticals/Adulterated",
    ),
    (
        "Little Moon Essentials, LLC",
        "Division of Pharmaceutical Quality Operations II",
        "CGMP/Finished Pharmaceuticals/Adulterated",
    ),
    (
        "Wittman Pharma, Inc.",
        "Division of Pharmaceutical Quality Operations II",
        "CGMP/Finished Pharmaceuticals/Adulterated",
    ),
    (
        "kdc/one Chatsworth, Inc.",
        "Center for Drug Evaluation and Research (CDER)",
        "CGMP/Finished Pharmaceuticals/Adulterated",
    ),
    (
        "Empower Clinic Services, LLC dba Empower Pharmacy",
        "Center for Drug Evaluation and Research (CDER)",
        "CGMP/Finished Pharmaceuticals/Adulterated/Unapproved New Drug",
    ),
    (
        "Bausch & Lomb Inc.",
        "Center for Drug Evaluation and Research (CDER)",
        "CGMP/Finished Pharmaceuticals/Adulterated",
    ),
    (
        "Happy Farm Botanicals, Inc.",
        "Center for Drug Evaluation and Research (CDER)",
        "CGMP/Finished Pharmaceuticals/Adulterated",
    ),
]


def _golden(fixtures_dir: Path) -> list[dict[str, str]]:
    with (fixtures_dir / "collect" / "subjects_2026-09-27.csv").open(newline="") as f:
        return list(csv.DictReader(f))


def test_rules_match_golden_subjects(fixtures_dir: Path) -> None:
    rows = _golden(fixtures_dir)
    mismatches = [
        (r["subject"], r["expected_type"], letter_type(r["subject"]))
        for r in rows
        if (letter_type(r["subject"]) or "") != r["expected_type"]
    ]
    assert mismatches == []
    assert sum(int(r["letters"]) for r in rows if r["expected_type"]) == 674


def test_spot_check_rows_in_scope() -> None:
    for company, _office, subject in SPOT_CHECK:
        assert letter_type(subject) == "cgmp_finished", company
    ora = [c for c, office, _ in SPOT_CHECK if "Pharmaceutical Quality Operations" in office]
    assert len(ora) == 4


@pytest.mark.parametrize(
    ("subject", "expected"),
    [
        ("CGMP/QSR/Drug/Medical Devices/Adulterated", None),
        ("CGMP/Dietary Supplement/Adulterated", None),
        ("Unapproved New Drug/Compounding/Misbranding", "compounding"),
        ("CGMP/Active Pharmaceutical Ingredient (API)/Adulterated", "api"),
        ("CGMP/Finished Pharmaceutical/API/Adulterated", "api"),
        ("Finished Pharmaceuticals/Unapproved New Drug/Misbranded", "unapproved_misbranded"),
        ("Unapproved New Drugs/Misbranded", None),
        ("Nonprescription/OTC", None),
        ("cgmp/finished   pharmaceuticals<br />/Adulterated", "cgmp_finished"),
        ("", None),
    ],
)
def test_exclusions_win_and_order(subject: str, expected: str | None) -> None:
    assert letter_type(subject) == expected


def test_rules_sha_pinned() -> None:
    assert RULES_VERSION == 1
    assert rules_sha256() == PINNED_RULES_SHA256
