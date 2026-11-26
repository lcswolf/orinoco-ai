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


def test_mobile_navigation_is_keyboard_accessible_and_not_inert() -> None:
    """Mobile users can open, traverse and dismiss the navigation drawer."""
    html = (ROOT / "orinoco" / "static" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "orinoco" / "static" / "app.js").read_text(encoding="utf-8")
    css = (ROOT / "orinoco" / "static" / "app.css").read_text(encoding="utf-8")

    assert 'id="sidebar"' in html
    assert 'aria-controls="sidebar"' in html
    assert 'class="mobile-menu-icon"' in html
    assert 'aria-expanded="false"' in html
    assert 'id="sidebar-backdrop"' in html
    assert 'id="mobile-nav-close"' in html
    assert "mobileBrand.addEventListener(\"click\"" in script
    assert "sidebar.inert = mobile && !open" in script
    assert "mainPanel.inert = open" in script
    assert 'document.body.classList.toggle("mobile-nav-open", open)' in script
    assert 'event.key === "Escape"' in script
    assert 'event.key !== "Tab"' in script
    assert "focusable[focusable.length - 1]" in script
    assert ".sidebar.mobile-open" in css
    assert "a:focus-visible, button:focus-visible" in css


def test_mobile_topbar_fits_narrow_screens_and_keeps_status_accessible() -> None:
    """Compact mobile controls must retain accessible labels and status text."""
    html = (ROOT / "orinoco" / "static" / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "orinoco" / "static" / "app.css").read_text(encoding="utf-8")

    assert 'id="connection-status" role="status" aria-live="polite"' in html
    assert "@media (max-width: 480px)" in css
    assert ".delete-chat-action::before" in css
    assert ".connection > span:last-child" in css


def test_static_html_has_unique_ids_and_resolved_accessibility_references() -> None:
    """Labels and ARIA relationships must point to existing, unique elements."""
    import re

    html = (ROOT / "orinoco" / "static" / "index.html").read_text(encoding="utf-8")
    ids = re.findall(r'id="([^"]+)"', html)
    id_set = set(ids)
    assert len(ids) == len(id_set)

    references = []
    for attribute in ("for", "aria-controls", "aria-labelledby", "aria-describedby"):
        for value in re.findall(rf'{attribute}="([^"]+)"', html):
            references.extend(value.split())

    assert set(references) <= id_set


def test_every_form_control_has_an_accessible_name() -> None:
    """Inputs, selects and textareas need a label or an explicit ARIA name."""
    from html.parser import HTMLParser

    class FormControlParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.labels = set()
            self.controls = []

        def handle_starttag(self, tag, attrs):
            attributes = dict(attrs)
            if tag == "label" and attributes.get("for"):
                self.labels.add(attributes["for"])
            if tag in {"input", "select", "textarea"} and attributes.get("type") != "hidden":
                self.controls.append(attributes)

    html = (ROOT / "orinoco" / "static" / "index.html").read_text(encoding="utf-8")
    parser = FormControlParser()
    parser.feed(html)
    missing = [
        control
        for control in parser.controls
        if not control.get("aria-label")
        and not control.get("aria-labelledby")
        and control.get("id") not in parser.labels
    ]

    assert not missing, f"Form controls without accessible names: {missing}"


def test_private_memories_navigation_prompts_for_sign_in() -> None:
    """Unauthenticated users should receive a clear sign-in prompt, not a dead link."""
    script = (ROOT / "orinoco" / "static" / "app.js").read_text(encoding="utf-8")
    start = script.index('memoriesLink.addEventListener("click"')
    end = script.index('document.getElementById("memory-form")', start)
    handler = script[start:end]

    assert "if (!currentUser)" in handler
    assert "loginDialog.showModal()" in handler
    assert 'document.getElementById("login-username").focus()' in handler


def test_backup_key_is_generated_locally_and_cleared_when_settings_close() -> None:
    """The backup key stays in browser memory and works with direct IP/port access."""
    html = (ROOT / "orinoco" / "static" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "orinoco" / "static" / "app.js").read_text(encoding="utf-8")

    start = script.index('document.getElementById("backup-key-generate").addEventListener')
    end = script.index('document.getElementById("backup-key-copy").addEventListener', start)
    generator = script[start:end]

    assert "window.crypto?.getRandomValues" in generator
    assert "window.crypto.getRandomValues(randomBytes)" in generator
    assert 'window.btoa(binary).replace(/\\+/g, "-").replace(/\\//g, "_")' in generator
    assert "window.isSecureContext" not in generator
    assert not any(secret_sink in generator for secret_sink in ("fetch(", "localStorage", "sessionStorage", "console."))
    assert 'id="backup-key-value" type="text" readonly' in html
    assert 'id="backup-key-copy"' in html
    assert "value.select();" in script
    assert 'settingsDialog.addEventListener("close"' in script
    assert 'adminRecoveryDialog.addEventListener("close"' in script
