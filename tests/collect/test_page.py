"""looks_like_letter tells a real letter page from a block or challenge page."""

from pathlib import Path

from regintel.collect.page import looks_like_letter


def test_looks_like_letter(fixtures_dir: Path) -> None:
    assert looks_like_letter((fixtures_dir / "collect" / "letter_cgmp.html").read_bytes())
    assert not looks_like_letter((fixtures_dir / "collect" / "access_denied.html").read_bytes())
    assert not looks_like_letter(b"")
    assert not looks_like_letter(b"<html><title>Page Not Found | FDA</title></html>")
