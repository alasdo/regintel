from __future__ import annotations

import difflib
from typing import Any


def normalize_text(text: str | None) -> str:
    """Normalize text before comparison."""
    if not text:
        return ""
    return text.strip()


def diff_versions(old_sections: list, new_sections: list) -> list[dict[str, Any]]:
    """
    Compare two lists of section-like objects.

    Expected attributes on each section object:
    - section_number
    - full_text
    - version_date

    Returns a list of change dicts with:
    - section_number
    - type: modified | added | removed
    - raw_diff
    - old_text (optional)
    - new_text (optional)
    """
    old_map = {s.section_number: s for s in old_sections}
    new_map = {s.section_number: s for s in new_sections}

    all_section_numbers = set(old_map.keys()) | set(new_map.keys())
    changes: list[dict[str, Any]] = []

    def sort_key(sn: str) -> tuple[int, int]:
        # Supports values like "211.68" and falls back safely.
        if "." in sn:
            left, right = sn.split(".", 1)
            try:
                return int(left), int(right)
            except ValueError:
                return (10**9, 10**9)
        try:
            return int(sn), 0
        except ValueError:
            return (10**9, 10**9)

    for sn in sorted(all_section_numbers, key=sort_key):
        old = old_map.get(sn)
        new = new_map.get(sn)

        if old and new:
            old_text = normalize_text(old.full_text)
            new_text = normalize_text(new.full_text)

            if old_text == new_text:
                continue

            diff_lines = difflib.unified_diff(
                old_text.splitlines(),
                new_text.splitlines(),
                fromfile=f"{sn} ({old.version_date})",
                tofile=f"{sn} ({new.version_date})",
                lineterm="",
            )

            changes.append(
                {
                    "section_number": sn,
                    "type": "modified",
                    "raw_diff": "\n".join(diff_lines),
                    "old_text": old_text,
                    "new_text": new_text,
                }
            )

        elif new and not old:
            changes.append(
                {
                    "section_number": sn,
                    "type": "added",
                    "raw_diff": f"+++ Added section {sn}",
                    "new_text": normalize_text(new.full_text),
                }
            )

        elif old and not new:
            changes.append(
                {
                    "section_number": sn,
                    "type": "removed",
                    "raw_diff": f"--- Removed section {sn}",
                    "old_text": normalize_text(old.full_text),
                }
            )

    return changes