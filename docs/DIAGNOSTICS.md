# Diagnostics and Support Bundles

**Status: implemented in the repository; live deployment acceptance outstanding.** Structured stdout and bounded persistent logs, read-only diagnostics checks, an administrator-only diagnostics panel and a privacy-filtered support ZIP are present in `main` and covered by automated tests. The support bundle is built locally and contains allowlisted diagnostic results and event metadata; it deliberately excludes free-form log messages and exception text. A security review and live Pterodactyl/browser verification are still required.

## Goals

Orinoco should make troubleshooting possible through the Pterodactyl Panel and authenticated web interface, without routine SSH access or manual log copying. An administrator should be able to run a local diagnostic check, download one support ZIP, and choose to share it with a support person.

No diagnostic data is sent automatically. There is no external telemetry service.

## Operator experience

1. The Pterodactyl Console displays concise startup, warning and error messages.
2. The Orinoco administrator opens **Administration → Diagnostics**.
3. The page shows database, model-service, storage and disk-space checks with pass/warning/fail explanations.
4. **Run checks** performs bounded, read-only checks and reports pass/warning/fail with a short explanation.
5. **Download support bundle** sends a CSRF-protected POST request and creates a bounded ZIP in memory containing diagnostics, a manifest and allowlisted event metadata. The administrator downloads it and can review it before sharing.
6. The page explains what the bundle contains and reminds the administrator to review it before sharing.

A Panel-only fallback should also be documented for cases where the web interface is unavailable: the operator can retrieve bounded, redacted logs through the Pterodactyl Console/File Manager. Do not require Docker exec or SSH for routine diagnosis.

## Logging

- Use structured records with UTC timestamp, severity, component, event code and request/correlation ID.
- Send concise records to stdout/stderr for the Pterodactyl Console and rotate bounded local log files under the persistent data directory.
- Persistent logs live in the data/logs/orinoco.log directory beside the configured database, with three 1 MiB rotated backups.
- Log files are UTF-8 and restricted to owner read/write permissions (0600); the log directory is restricted to owner access (0700).
- Refuse a symlink at the active log-file or log-directory path.
- Apply the same credential-redaction filter to console and file handlers before records are emitted.
- If persistent storage is unavailable or read-only, Orinoco continues with console logging and emits a warning; logging failure must not prevent startup.
- Include stack traces for unexpected server-side exceptions, but pass all text through the redaction layer before persistence or export.
- Avoid logging request bodies, prompts, model replies, uploaded document contents, memory contents, cookies, authorization headers or credentials.
- Use stable event codes for common operational failures (database, migration, model startup/download, model request, backup, restore, scheduler, web research and optional integrations).

## Support bundle contents

Include only bounded, allowlisted diagnostics:

- Orinoco version, validated source commit when supplied by the deployment, Python version, operating-system family and architecture. Image digests and image build metadata are not currently available to the application exporter.
- Database schema version and a read-only database integrity/availability result; never the database file itself.
- Health/readiness status and component check outcomes.
- Sanitized configuration summary: validated feature enabled/disabled flags, selected model name, context setting and timezone. Invalid values are omitted; raw environment values, credentials and filesystem paths are not exported.
- A bounded sample of recent structured event metadata (timestamp, level, logger, event code and request ID). Free-form messages and exception text are deliberately excluded from the ZIP.
- Backup scheduler history is not included in this first iteration; it will be added after its data and privacy boundaries are reviewed.
- Disk availability for relevant data paths when supported.
- A manifest describing bundle creation time, included files, truncation and redaction policy.

Never include:
- Passwords, password hashes, session tokens, cookies, CSRF tokens, recovery/bootstrap tokens, API keys, Discord tokens, backup encryption keys or S3 credentials.
- Private or shared conversation messages, prompts, model replies, personal memories, document contents, original uploads or database snapshots.
- Raw environment dumps, full request headers, arbitrary process command lines or unrestricted filesystem listings.
- Private IPs, hostnames or URLs unless explicitly necessary and separately disclosed; prefer safe summaries.

## Security requirements

- Admin-only endpoints and UI; enforce authorization server-side on every request.
- CSRF protection for state-changing/generation actions, including the support-bundle POST endpoint.
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
- Backup scheduler state and last success/failure (planned follow-up; not yet surfaced by the current diagnostics panel).
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

1. Structured logger, correlation IDs, redaction and bounded rotation. (Implemented; verify operational behaviour on a disposable Panel instance.)
2. Diagnostics service and read-only self-checks. (Implemented and covered by automated tests.)
3. Admin-only diagnostics panel and downloadable ZIP. (Implemented and covered by automated tests.)
4. Adversarial privacy/security review and Panel-first documentation. (Initial tests cover ZIP contents, metadata allowlisting and symlink rejection; broader review remains.)
5. Live disposable Pterodactyl test, including the web-UI-unavailable fallback. (Outstanding.)

Do not mark the feature complete until the support ZIP has been inspected for secrets and private content and the complete workflow has been exercised on a disposable Panel instance.
