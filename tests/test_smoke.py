"""Smoke test: the package imports and exposes a version. Replace with real tests."""

import regintel


def test_package_exposes_semver_version() -> None:
    parts = regintel.__version__.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)
