# Administrator-managed identity and behaviour configuration

**Status: first implementation available in PR #26; further lifecycle and acceptance work remains.**

## Purpose

Orinoco's identity belongs to the application, not to a particular inference model. Administrators can define who Orinoco is, who built it, why it exists and how it communicates. The profile is persisted in the application database and is separate from per-user preferences and model-specific settings.

## Implemented in the first increment

The administrator **Identity & Behaviour** area includes:

- Assistant name, creator, organisation, purpose, background and introduction.
- Optional HTTPS project URL (stored only; it is not fetched automatically).
- Core personality and advanced style guidance with length limits.
- Humour, warmth, formality and patience sliders (0–100).
- Response-length preference and Welsh/English language policy.
- Administrator-only profile read/save APIs, with server-side role checks and CSRF protection on writes.
- Validated, version-numbered active and pending profiles stored in SQLite.
- Changes are saved as **Pending restart**. Startup validates and promotes the pending profile; the chat prompt uses the active profile.
- The active profile remains in place until activation. Identity activation errors are logged and do not intentionally prevent application startup.
- Identity fields are style/context only. They cannot grant capabilities or override application-owned safety, privacy or access-control rules.

The profile has safe defaults and does not require optional fields to be filled in. Standard users cannot access the shared identity API or administrator controls.

## Personality and language

Welsh and English remain first-class. The initial language choices are:

- Follow the user's language.
- Welsh by default.
- English by default.

The active profile is added to the model-independent chat prompt. Existing per-user language and response preferences remain separate. This first increment provides basic language policy and style guidance; more detailed code-switching controls and model acceptance tests remain future work.

## Persistence and lifecycle

- The profile is stored in the application database, not in the container image or model files.
- Each saved pending profile receives a version number and update timestamp.
- The administrator can see active/pending version information.
- Startup revalidates the pending profile before promotion.
- Do not store secrets in identity fields.

**Not yet implemented:** a profile history/archive, administrator rollback UI, profile preview, backup/restore verification specific to identity, and model-upgrade acceptance testing. Version numbers in this first increment identify active/pending revisions; they are not a complete rollback history.

## Protected policy and prompt assembly

Identity and personality text is contextual guidance only. It must not be treated as a source of permissions or as a replacement for protected application policy. Keep safety, privacy, account isolation, tool permissions and administrator boundaries in application-owned prompt and code paths.

User memories, documents, web pages and retrieved material remain untrusted content, not instructions. The prompt builder remains model-agnostic; model adapters may translate supported inference parameters but do not own or persist Orinoco's identity.

## Future work

1. Add profile history and a safe rollback workflow.
2. Add preview and clearer effective-profile diagnostics.
3. Add backup/restore coverage and migration verification.
4. Add model-upgrade acceptance tests for identity, tone, Welsh/English behaviour, privacy and capability honesty.
5. Improve language/code-switching guidance and any supported voice integration.

Do not change VPS, Panel, Wings, game-server or external infrastructure as part of this feature. Do not publish an image or deploy automatically.
