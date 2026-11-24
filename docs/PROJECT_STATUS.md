# Project Status

**Overall status: early implementation — custom interface, local model runtime, authentication, private chat, personal memory and document-library milestones committed.**

This page separates confirmed project decisions from implementation work. A planned feature is not considered implemented until code, tests and documentation exist.

## Implemented in the repository

- Public project repository and project documentation.
- Custom responsive Orinoco interface, served directly by FastAPI.
- Sign-in, secure signed sessions, CSRF-protected authentication and password changes.
- Administrator account management: create standard users, list users, suspend and reactivate accounts.
- Authenticated chat with local Ollama, saved per-user conversations and conversation switching.
- Single-generation queue, bounded model output and a short conversation context window.
- Per-user personal memories with automatic extraction, review, correction and deletion.
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
- Automated Python tests and frontend JavaScript syntax validation.

The latest completed GitHub Actions Python test run passed 118 tests, including first-admin bootstrap, bounded login throttling, account-wide session revocation, sensitive-memory filtering, loopback-only inference enforcement, Office archive expansion limits, SSRF redirect and response-size protections, encrypted backup upload/restore, document cleanup failure handling, storage path traversal/symlink protection, browser security headers, timezone configuration and SQLite schema upgrade protection. The latest audit-hardened custom container image, including account-wide session revocation and document-storage hardening, has built and passed its expanded runtime smoke test. No image has been published to GHCR or tested on a live Pterodactyl node.

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

- Automatic daily backup scheduling, retention and remote restore convenience; safe application update/rollback.
- Conversation deletion/editing, pagination and streaming responses.
- Advanced semantic/vector document search and OCR for scanned PDFs.
- Original Womble-inspired mascot artwork and final UK-oriented interface treatment.
- Administrator-editable core personality and per-user voice, tone and answer-detail preferences.
- Discord integration and voice features.
- Production-ready image publication, live Egg import and Pterodactyl node deployment.
- Production security review, MFA, account recovery and server-side session revocation across all devices.

## Next implementation sequence

1. Complete the repository-wide pre-release audit and re-run the final image build/smoke test.
2. Add automatic daily backup scheduling and retention, including failure visibility.
3. Add safe application update, database migration and rollback tooling.
4. Add Discord text integration; consider voice only after the core is stable.
5. Publish the stable image and import/test the finished Egg on the user's Panel.

## Resource assumptions

The previously discussed target VPS has 4 vCPU and 6 GiB RAM. The proposed initial container allowance is approximately 4 GiB RAM, with one model generation at a time. These are planning values, not validated minimum requirements. Automatic memory extraction uses a second local model request after a chat reply, so it increases response time and can be disabled with AUTO_SAVE_MEMORIES=false.

## Release policy

The intended update channel is stable. Releases should be versioned, documented and tested. Database migrations must be backed up and have a documented recovery path.
