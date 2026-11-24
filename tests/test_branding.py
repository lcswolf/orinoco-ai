"""Regression checks for Orinoco's accessible woodland-themed interface."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_original_woodland_mascot_is_integrated_with_accessible_text() -> None:
    """The welcome screen uses the original mascot asset and provides meaningful alt text."""
    html = (ROOT / "orinoco" / "static" / "index.html").read_text(encoding="utf-8")
    artwork = (ROOT / "orinoco" / "static" / "mascot.svg").read_text(encoding="utf-8")

    assert 'src="/static/mascot.svg"' in html
    assert 'alt="Orinoco, a cheerful woodland helper"' in html
    assert "<title id=\"title\">Orinoco woodland helper mascot</title>" in artwork
    assert "<desc id=\"desc\">" in artwork
    assert "<script" not in artwork.lower()
    assert "https://" not in artwork


def test_woodland_mascot_has_responsive_styling_and_uk_copy() -> None:
    """The character remains sized on small screens and the welcome copy reflects the UK theme."""
    html = (ROOT / "orinoco" / "static" / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "orinoco" / "static" / "app.css").read_text(encoding="utf-8")

    assert "British woodland charm" in html
    assert "UK time" in html
    assert ".welcome-mascot" in css
    assert ".welcome-mark { width: 126px; height: 126px;" in css
    assert "--mint: #a0c78b" in css
