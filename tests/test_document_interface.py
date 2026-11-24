"""Static checks for the document library interface."""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def test_document_library_controls_match_api_routes() -> None:
    html = (ROOT / "orinoco/static/index.html").read_text(encoding="utf-8")
    script = (ROOT / "orinoco/static/app.js").read_text(encoding="utf-8")

    for element_id in (
        "documents-link",
        "documents-view",
        "private-document-form",
        "private-document-file",
        "private-document-list",
        "shared-document-tools",
        "shared-document-form",
        "shared-document-file",
        "shared-document-list",
    ):
        assert f'id="{element_id}"' in html

    assert '"/api/documents"' in script
    assert '"/api/admin/shared-documents"' in script
    assert '"/api/documents/"' in script
    assert '"/api/admin/shared-documents/"' in script
    assert "10 * 1024 * 1024" in script


def test_document_library_is_not_available_before_sign_in() -> None:
    html = (ROOT / "orinoco/static/index.html").read_text(encoding="utf-8")
    assert 'id="documents-view"' in html
    assert 'id="shared-document-tools" aria-labelledby="shared-documents-heading" hidden' in html
    assert 'id="documents-link"' in html



def test_document_interface_has_unique_ids_and_single_controller() -> None:
    html = (ROOT / "orinoco/static/index.html").read_text(encoding="utf-8")
    script = (ROOT / "orinoco/static/app.js").read_text(encoding="utf-8")
    ids = re.findall(r'\bid="([^"]+)"', html)
    assert ids
    assert len(ids) == len(set(ids))
    assert script.count('const documentsLink =') == 1
    assert "function loadSharedDocuments" not in script
    assert 'document.getElementById("document-list")' not in script
