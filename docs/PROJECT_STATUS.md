# Project Status

**Overall status: early implementation — custom interface, local model runtime, authentication, private chat, personal memory and document-library milestones committed.**

This page separates confirmed project decisions from implementation work. A planned feature is not considered implemented until code, tests and documentation exist.

## Implemented in the repository

- Public project repository and project documentation.
- Custom responsive Orinoco interface, served directly by FastAPI, with an original Womble-inspired woodland helper mascot, woodland-green/brass accents and UK-friendly copy.
- Owner-only conversation deletion with CSRF protection, explicit confirmation and cascading message removal.
- Bounded login throttling per username and observed client address; forwarded-IP headers are not trusted.
- SQLite database files use owner-only permissions and symbolic-link paths are rejected.
- External search links are revalidated in the browser and filtered server-side to exclude obvious local/private destinations.
- Sign-in, secure signed sessions, CSRF-protected authentication and password changes.
- Administrator account management: create standard users, list users, suspend and reactivate accounts.
- Authenticated chat with local Ollama, saved per-user conversations and conversation switching.
- Single-generation queue, bounded model output and a short conversation context window.
- Per-user personal memories with automatic extraction, review, correction and deletion; automatic extraction can be disabled independently by each user.
- Per-user response voice, tone, answer-detail and automatic-memory opt-out preferences, stored privately and applied to local chat prompts.
- Administrator-managed shared core personality and configurable humour level (default 65%).
- Memory and document reference context is supplied separately from system instructions and treated as untrusted data.
- Private document uploads with per-account storage, bounded text extraction, download and deletion.
- Administrator-managed shared document library, read-only to standard users.
- Supported document formats: TXT, Markdown, PDF, DOCX, XLSX and PPTX, up to 10 MiB per file.
- SQLite FTS5 keyword retrieval from the current user's private documents and authorised shared documents.
- Explicit authenticated web-search workspace and per-message opt-in web search in chat, using an administrator-configured SearXNG endpoint.
- User-triggered public webpage summarisation using local Ollama, with DNS-pinned public-IP resolution, blocked private/local addresses, redirect validation and bounded response sizes.
- Liveness endpoint /healthz and local-model readiness endpoint /readyz.
- Non-root Pterodactyl runtime foundation, pinned Ollama CPU runtime, process supervision and automatic model download.
- Preview Pterodactyl 1.x Egg definition for Panel 1.13.0.
- Encrypted local backup creation, verification and confirmed restore CLI using AES-256-GCM.
- S3-compatible encrypted backup upload over HTTPS, with remote size, metadata and downloaded-byte SHA-256 verification; restore keeps pre-restore database, document and session-secret recovery copies.
- Supervised daily encrypted backup scheduler (03:00 in the configured timezone by default), optional verified S3 upload, configurable 1–365 day local retention and persistent failure status.
- Session-secret symlink rejection and restrictive file permissions; safe backup restore recovery-path checks.
- CI dependency vulnerability audit and weekly Dependabot monitoring for Python packages and GitHub Actions.
- Operator runbook for manual image updates, one-shot backup/restore commands and rollback sequencing; backup-verified update preparation and explicit SQLite migration CLI.
- Automated Python tests, frontend JavaScript syntax validation and dependency vulnerability audit.

The previous completed GitHub Actions Python test run passed 170 tests, with one non-failing Starlette/httpx TestClient deprecation warning. The subsequent per-user automatic-memory preference change is undergoing CI validation; do not treat the earlier count as validation of the current commit. Coverage includes first-admin bootstrap, login throttling, account-wide session revocation, sensitive-memory filtering, loopback-only inference, Office archive expansion limits, SSRF redirect/response-size protections, encrypted backup upload/restore, document cleanup and storage-path protection, browser security headers, timezone configuration, SQLite schema upgrades, daily backup scheduling/retention, Egg wiring, chat recovery when memory persistence fails, owner-scoped conversation deletion, login IP throttling, database file protections, external-link safety, v5-to-v6 migration, per-user preference isolation, admin persona permissions and prompt integration, and mascot/accessibility checks. The latest image with the scheduler, mascot, conversation deletion, schema v6 and persona settings has built and passed its runtime smoke test. The final CLI error-handling adjustment is being rebuilt. No image has been published to GHCR or tested on a live Pterodactyl node.

## Confirmed direction

- Self-hosted assistant named Orinoco.
- Fully custom Orinoco web interface; Open WebUI will not be used as the main frontend.
- Local model inference; no external AI inference API is intended.
- Ollama is the inference runtime, currently pinned to version 0.40.18 in the image.
- Initial target is a modest Ubuntu 24.04 LTS VPS.
- Pterodactyl Panel 1.13.0 is the target deployment manager.
- Stable releases are preferred for updates.
- Curated model list: Qwen 2.5 0.5B, 1.5B and 3B; 1.5B is the default.
- Initial context target is 2048 tokens and one model request at a time.
- Discord text integration is planned; voice listening must require explicit activation.
- Private chats, memories and documents must be isolated per account.
- Public registration should be disabled by default.

## Not implemented yet

- Remote bucket lifecycle retention and restore-from-remote convenience; automated image switching and a live update/rollback drill (a manual operator runbook and backup-gated migration CLI are implemented).
- Conversation editing, pagination and streaming responses.
- Advanced semantic/vector document search and OCR for scanned PDFs.
- Discord integration and voice features.
- Production-ready image publication, live Egg import and Pterodactyl node deployment.
- Production security review, MFA/account recovery, reverse-proxy-level rate limits, trusted-proxy configuration and resource quotas.

## Next implementation sequence

1. Finish the repository-wide pre-release audit and final scheduler/mascot/conversation-deletion container smoke test.
2. Finish accessibility/mobile polish and review the new persona settings on a live test instance.
3. Validate the update/rollback runbook on a disposable Pterodactyl server and perform a real backup/restore drill.
4. Validate the Egg on a disposable server in the user's Panel.
5. Publish a versioned stable image only after the live deployment and recovery release gates pass; Discord and voice follow later.

## Resource assumptions

The previously discussed target VPS has 4 vCPU and 6 GiB RAM. The proposed initial container allowance is approximately 4 GiB RAM, with one model generation at a time. These are planning values, not validated minimum requirements. Automatic memory extraction uses a second local model request after a chat reply, so it increases response time and can be disabled with AUTO_SAVE_MEMORIES=false.

## Release policy

The intended update channel is stable. Releases should be versioned, documented and tested. Database migrations must be backed up and have a documented recovery path.
