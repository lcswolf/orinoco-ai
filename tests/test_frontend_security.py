"""Security regression checks for rendering untrusted browser content."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_frontend_never_inserts_untrusted_text_as_html() -> None:
    """Chat, documents, memories and search snippets must use text nodes, not HTML parsing."""
    script = (ROOT / "orinoco" / "static" / "app.js").read_text(encoding="utf-8")

    for unsafe_api in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("):
        assert unsafe_api not in script
    assert "body.textContent = content" in script
    assert "summary.textContent = result.content" in script


def test_external_links_are_restricted_to_credential_free_http_urls() -> None:
    """Untrusted SearXNG and summary URLs must pass the same browser-side protocol check."""
    script = (ROOT / "orinoco" / "static" / "app.js").read_text(encoding="utf-8")

    assert "function safeExternalUrl(value)" in script
    assert '["http:", "https:"]' in script
    assert "parsed.username || parsed.password" in script
    assert "const safeUrl = safeExternalUrl(result.url)" in script
    assert "link.href = safeUrl" in script
    assert "source.href = safeSourceUrl" in script
    assert "link.href = result.url" not in script


def test_conversation_delete_control_is_explicit_and_csrf_protected() -> None:
    """The UI asks for confirmation and uses the authenticated DELETE endpoint."""
    html = (ROOT / "orinoco" / "static" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "orinoco" / "static" / "app.js").read_text(encoding="utf-8")

    assert 'id="delete-chat-action"' in html
    assert 'aria-label="Delete current conversation"' in html
    assert "window.confirm(" in script
    assert 'method: "DELETE"' in script
    assert 'headers: { "X-CSRF-Token": csrf, Accept: "application/json" }' in script
    assert '"/api/conversations/" + encodeURIComponent(conversationId)' in script


def test_response_preferences_and_admin_persona_controls_are_accessible() -> None:
    """The UI exposes account preferences to users and core persona controls to admins."""
    html = (ROOT / "orinoco" / "static" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "orinoco" / "static" / "app.js").read_text(encoding="utf-8")

    assert 'id="preferences-form"' in html
    assert 'id="preference-voice"' in html
    assert 'id="preference-tone"' in html
    assert 'id="preference-detail"' in html
    assert 'id="admin-persona-tools" hidden' in html
    assert 'id="core-persona"' in html
    assert 'id="humour-level"' in html
    assert 'fetch("/api/preferences"' in script
    assert 'fetch("/api/admin/persona"' in script
    assert 'method: "PUT"' in script
