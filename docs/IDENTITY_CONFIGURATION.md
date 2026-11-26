# Administrator-managed identity and behaviour configuration

**Status: approved design; implementation not yet complete.**

## Purpose

Orinoco's identity must belong to the application, not to a particular inference model. Administrators should be able to define who Orinoco is, who built it, why it exists and how it communicates. The same identity must survive model changes, application restarts, upgrades, backups and migration to another machine.

The current administrator persona controls a short shared persona instruction and humour level. This design expands that foundation into a versioned identity profile without mixing it with per-user preferences or model-specific settings.

## Administrator experience

Add an **Identity & Behaviour** area to the administrator settings. It is not visible or writable to standard users. Every API endpoint must enforce administrator authorisation server-side; hiding the controls in JavaScript is not an access control.

### Identity

- Assistant display name (default: Orinoco)
- Creator / built by (free text; optional)
- Organisation / publisher (optional)
- Purpose / intended role
- Background / origin story
- Short introduction used when asked who the assistant is
- Optional website or project URL (plain text/validated HTTPS URL; never fetched automatically)

### Personality and communication

- Core personality guidance
- Humour level (0–100)
- Warmth / friendliness
- Formality (casual to professional)
- Patience / explanation detail
- Response length preference
- Voice preference where a supported voice module exists

Keep the initial controls understandable. Advanced prompt text belongs in a clearly separated advanced section and must have a strict length limit.

### Language and model-independent behaviour

- Supported languages and default language policy (Welsh and English remain first-class)
- Whether to follow the language of the latest user message
- Code-switching guidance
- British English conventions where relevant
- Behavioural guidance that does not grant capabilities or permissions

### Protected policy

Safety, privacy, account isolation, tool permissions and administrator boundaries are not ordinary personality fields. Keep these in application-owned, reviewed prompt sections that administrators cannot weaken through free-text persona instructions. Identity and personality content is style/context only and must never override system guardrails or grant tools, access or privileges.

## Persistence and lifecycle

- Store the profile persistently in Orinoco's application data/database, not in the container image, environment-only settings or a particular model's files.
- Version every saved profile and record update time. Do not store secrets in the profile.
- Keep the last known-good profile so an administrator can roll back.
- Validate and save changes as **Pending restart**. The currently loaded profile remains **Active** until a controlled restart.
- At startup, load and validate the pending profile, then promote it to active. If validation fails, retain the last known-good active profile and report a safe diagnostic event; do not prevent the service from starting solely because optional identity text is invalid.
- Expose active and pending version/status to administrators. Never expose internal prompt text to ordinary users or public unauthenticated endpoints.
- Preserve the profile across application image updates, model downloads, model swaps, VPS resizing and migration. Include it in encrypted application backups and restore verification.
- First installation uses safe defaults and does not require an administrator to fill every optional identity field.

## Prompt assembly and model independence

Build the effective system instruction at request time from separate, ordered sections:

1. Application-owned safety, privacy and capability guardrails.
2. Application-owned assistant identity and role boundary.
3. Active administrator identity profile and personality guidance.
4. The signed-in user's own allowed response preferences.
5. Relevant conversation context and retrieved reference material, clearly marked as untrusted data.

User memories, documents, web pages and other retrieved material are never instructions. Administrator identity/personality fields must not be able to replace the protected guardrails or create capabilities that the application has not implemented.

The prompt builder must be model-agnostic. Model-specific adapters may translate supported inference parameters, but must not own or persist Orinoco's identity.

## Model upgrade continuity

Changing the selected local model must leave the identity profile, user preferences, conversations and memories untouched. Provide a repeatable model acceptance test covering:

- Name, creator and purpose are represented accurately.
- Friendly/helpful tone and configured humour level.
- Patient explanations and requested response detail.
- Welsh, English and natural code-switching.
- Respect for privacy, user separation and protected policy.
- Refusal to claim tools or capabilities that are not enabled.

Show test results and allow an administrator to keep the existing model if the candidate behaves materially worse. Do not silently rewrite the identity profile to compensate for a new model.

## User-level preferences remain separate

Standard users may continue to control only their own permitted preferences (for example, voice, tone, answer detail and language). Those choices may personalise delivery but cannot change the shared identity, purpose, protected policies, model selection or another user's data.

## Initial implementation sequence

1. Expand the existing persisted administrator persona into a versioned identity profile and add validation/defaults/migration tests.
2. Add administrator-only read/update/preview APIs, CSRF protection for writes, pending/active status and rollback.
3. Add responsive Identity & Behaviour controls to the existing administrator settings UI.
4. Assemble the active profile into the model-independent prompt while keeping protected guardrails separate.
5. Add startup activation, safe fallback, audit/diagnostic events and backup/restore coverage.
6. Add model-upgrade acceptance tests and documentation.

Do not change VPS, Panel, Wings, game-server or external infrastructure as part of this feature. Do not publish an image or deploy automatically.
