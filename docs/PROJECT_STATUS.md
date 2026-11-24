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
- Configurable per-user/shared document count and byte quotas, application declared-body limits, and per-user chat submission throttling; reverse-proxy enforcement is documented but not deployed.
- Bounded in-flight chat admission (one active generation plus up to eight additional requests by default); overload is rejected with HTTP 503 instead of accumulating an unbounded queue.
- Configurable per-user personal-memory count cap (100 by default), with atomic quota enforcement and graceful automatic-extraction behaviour when full.
- Network deployment design for Caddy public TLS, Nginx loopback edge limits, HTTPS public-IP access and private Tailscale Serve; Uvicorn forwarded-header trust is disabled by default.

The latest completed GitHub Actions Python test run passed **183 tests** with one non-failing Starlette/httpx TestClient deprecation warning. The run includes the request-body guard, document byte/count quotas, per-user chat throttling, bounded generation admission, per-user memory quotas, sensitive-memory/prompt-injection filtering, Egg resource-variable checks and reverse-proxy template checks. [Tests run #699](https://github.com/lcswolf/orinoco-ai/actions/runs/45489328171) passed on commit `20462c11`. The container build/smoke test [run #333](https://github.com/lcswolf/orinoco-ai/actions/runs/45489210151) is validating the runtime changes and must finish before this status is updated to a successful build. The image has not been published to GHCR or deployed to Pterodactyl.

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
- Host-level Caddy/Nginx configuration, firewall rules, certificate issuance/renewal and Tailscale Serve are documented but not applied or tested on the Leaseweb VPS.
- Production security review, MFA/account recovery, live trusted-proxy configuration, chat retention and multi-worker quota coordination.

## Next implementation sequence

1. Finish the repository-wide pre-release audit and repeat the Python tests and container smoke test on the latest commit.
2. Apply the Caddy/Nginx network design on the actual Leaseweb VPS, including Docker/Wings firewall rules, subdomain and IP certificate issuance, edge limits and private Tailscale Serve.
3. Validate the Egg on a disposable server in Panel 1.13.0 and test the proxy-to-allocation path.
4. Perform a real encrypted backup/restore and update/rollback drill on the disposable Pterodactyl server.
5. Finish accessibility/mobile polish and review account settings on the live test instance.
6. Publish a versioned stable image only after the live deployment and recovery release gates pass; Discord and voice follow later.

## Resource assumptions

The previously discussed target VPS has 4 vCPU and 6 GiB RAM. The proposed initial container allowance is approximately 4 GiB RAM, with one model generation at a time. These are planning values, not validated minimum requirements. Automatic memory extraction uses a second local model request after a chat reply, so it increases response time and can be disabled with AUTO_SAVE_MEMORIES=false.

## Release policy

The intended update channel is stable. Releases should be versioned, documented and tested. Database migrations must be backed up and have a documented recovery path.
