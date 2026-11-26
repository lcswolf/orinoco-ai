# Diagnostics and Support Bundles

**Status: proposed implementation specification.** This document defines the privacy and operational requirements for diagnostics. It is not a claim that the feature is implemented.

## Goals

Orinoco should make troubleshooting possible through the Pterodactyl Panel and authenticated web interface, without routine SSH access or manual log copying. An administrator should be able to run a local diagnostic check, download one support ZIP, and choose to share it with a support person.

No diagnostic data is sent automatically. There is no external telemetry service.

## Operator experience

1. The Pterodactyl Console displays concise startup, warning and error messages.
2. The Orinoco administrator opens **Administration → Diagnostics**.
3. The page shows service health, readiness, recent error counts and the last successful/failed backup status.
4. **Run checks** performs bounded, read-only checks and reports pass/warning/fail with a short explanation.
5. **Download support bundle** creates a timestamped ZIP locally. The administrator downloads it and can attach it to a support conversation.
6. The page explains what the bundle contains and reminds the administrator to review it before sharing.

A Panel-only fallback should also be documented for cases where the web interface is unavailable: the operator can retrieve bounded, redacted logs through the Pterodactyl Console/File Manager. Do not require Docker exec or SSH for routine diagnosis.

## Logging

- Use structured records with UTC timestamp, severity, component, event code and request/correlation ID.
- Send concise records to stdout/stderr for the Pterodactyl Console and rotate bounded local log files under the persistent data directory.
- Include stack traces for unexpected server-side exceptions, but pass all text through the redaction layer before persistence or export.
- Avoid logging request bodies, prompts, model replies, uploaded document contents, memory contents, cookies, authorization headers or credentials.
- Use stable event codes for common operational failures (database, migration, model startup/download, model request, backup, restore, scheduler, web research and optional integrations).
- Configure a conservative retention and size cap; logging failure must not crash the application.

## Support bundle contents

Include only bounded, allowlisted diagnostics:

- Orinoco version/commit, image/runtime version, Python version, platform and architecture.
- Database schema version and a read-only database integrity/availability result; never the database file itself.
- Health/readiness status and component check outcomes.
- Sanitized configuration summary: feature enabled/disabled flags, selected model name, context setting, timezone and configured storage paths represented safely.
- Recent redacted application logs and bounded startup/Panel-console diagnostic excerpts where available.
- Recent backup job status and timestamps, without archive contents, keys, bucket credentials or private object URLs.
- Disk availability for relevant data paths when supported.
- A manifest describing bundle creation time, included files, truncation and redaction policy.

Never include:
- Passwords, password hashes, session tokens, cookies, CSRF tokens, recovery/bootstrap tokens, API keys, Discord tokens, backup encryption keys or S3 credentials.
- Private or shared conversation messages, prompts, model replies, personal memories, document contents, original uploads or database snapshots.
- Raw environment dumps, full request headers, arbitrary process command lines or unrestricted filesystem listings.
- Private IPs, hostnames or URLs unless explicitly necessary and separately disclosed; prefer safe summaries.

## Security requirements

- Admin-only endpoints and UI; enforce authorization server-side on every request.
- CSRF protection for state-changing/generation actions.
- Build bundles from an explicit allowlist, never by archiving a user-supplied path or the whole data directory.
- Resolve paths beneath a fixed diagnostics root; reject symlinks and non-regular files.
- Use atomic temporary-file creation, restrictive permissions, bounded concurrent generation and automatic cleanup/expiry.
- Apply a strict maximum log age, per-file size, total uncompressed size and ZIP size.
- Redact secrets before logs are written and again before bundle export (defence in depth). Redaction must handle common key/value formats, bearer credentials, URL user-info and known configured secret values.
- If redaction cannot confidently sanitize a diagnostic field, omit the field rather than export it.
- Never upload bundles automatically; sharing is an explicit administrator action outside Orinoco.

## Diagnostic checks

Checks should be read-only, time-bounded and report useful explanations:

- Database can be opened; expected schema version; integrity check outcome.
- Ollama process/API reachable; configured model present; model readiness state.
- Required persistent directories exist and are writable.
- Disk space for data and model storage where the platform exposes it.
- Backup scheduler state, last attempt, last success/failure and local backup availability.
- Optional integrations only when enabled; report disabled integrations as skipped, not failed.
- Application liveness/readiness and process supervisor status where available.

Checks must not trigger model downloads, modify user data, run migrations, perform restores or contact external services beyond the configured local integration health endpoints.

## Tests and acceptance criteria

- A synthetic exception is recorded with a correlation ID and a useful stack trace.
- Known test secrets in headers, URLs, nested structures and exception messages are redacted before disk persistence and bundle export.
- Synthetic private chat, memory and document strings never appear in a generated bundle.
- Bundle contains expected metadata/log/check files and can be opened as a ZIP.
- Non-admin users receive an authorization failure for diagnostics and download routes.
- CSRF, path traversal, symlink, oversized file, concurrent generation and cleanup cases are tested.
- Rotation and total bundle limits are enforced.
- Diagnostic check timeouts do not hang the web application.
- Pterodactyl Console receives useful startup and error output.
- Documentation explains how to generate, review, download and share the bundle through the Panel.

## Delivery sequence

1. Structured logger, correlation IDs, redaction and bounded rotation.
2. Diagnostics service and read-only self-checks.
3. Admin-only diagnostics page and downloadable ZIP.
4. Adversarial privacy/security tests and Panel-first documentation.
5. Live disposable Pterodactyl test, including web UI unavailable fallback.

Do not mark the feature complete until the support ZIP has been inspected for secrets and private content and the complete workflow has been exercised on a disposable Panel instance.
