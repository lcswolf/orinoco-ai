# Project Status

**Overall status: active development / staging preview — the custom interface, local model runtime, authentication, private chat, personal memory, document library, administrator identity profile and container-aware resource detection are implemented. Live deployment and release gates remain outstanding.**

This page separates confirmed project decisions from implementation work. A planned feature is not considered implemented until code, tests and documentation exist.

## Implemented in the repository

- Public project repository, technical documentation and a step-by-step preview user/setup guide covering host preparation, Egg installation, configuration, first-admin setup, app usage, backups and troubleshooting.
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
- Administrator-managed, model-independent identity profile covering assistant name, creator, organisation, purpose, background, introduction, project URL, personality, humour, warmth, formality, patience, response length, language policy and advanced style guidance. Changes are saved as pending and activated on application startup; identity text is contextual guidance and cannot override protected safety or privacy rules.
- Container-aware resource detection for cgroup v1/v2 CPU and memory limits, process CPU affinity, available memory and usage; Ollama inference thread selection respects detected CPU limits and a bounded `AI_THREADS` administrator override.
- Memory and document reference context is supplied separately from system instructions and treated as untrusted data.
- Private document uploads with per-account storage, bounded text extraction, download and deletion.
- Administrator-managed shared document library, read-only to standard users.
- Supported document formats: TXT, Markdown, PDF, DOCX, XLSX and PPTX, up to 10 MiB per file.
- SQLite FTS5 keyword retrieval from the current user's private documents and authorised shared documents.
- Explicit authenticated web-search workspace and per-message opt-in web search in chat, using an administrator-configured SearXNG endpoint.
- User-triggered public webpage summarisation using local Ollama, with DNS-pinned public-IP resolution, blocked private/local addresses, redirect validation and bounded response sizes.
- Liveness endpoint /healthz and local-model readiness endpoint /readyz.
- Non-root Pterodactyl runtime foundation, pinned Ollama CPU runtime, process supervision and automatic model download; first-run pulls retry transient failures up to three times before failing visibly.
- Preview Pterodactyl 1.x Egg definition for Panel 1.13.0; live import validation remains outstanding.
- Encrypted local backup creation, verification and confirmed restore CLI using AES-256-GCM.
- S3-compatible encrypted backup upload over HTTPS, with remote size, metadata and downloaded-byte SHA-256 verification; restore keeps pre-restore database, document and session-secret recovery copies.
- Optional supervised encrypted backup scheduler (disabled by default), with a configurable schedule, optional verified S3 upload, configurable 1–365 day local retention and persistent failure status.
- Session-secret symlink rejection and restrictive file permissions; safe backup restore recovery-path checks.
- CI dependency vulnerability audit and weekly Dependabot monitoring for Python packages and GitHub Actions. GitHub Actions are pinned to immutable commit SHAs; Python runtime and development dependencies are now compiled into SHA-256 hash-locked requirements files; CI and the Docker image install them with `--require-hashes`.
- Operator runbook for manual image updates, one-shot backup/restore commands and rollback sequencing; backup-verified update preparation and explicit SQLite migration CLI.
- Panel-first administrator setup and recovery are implemented in `main`: token-gated first-admin creation, expiring one-time recovery with session revocation, and a browser-only backup-key generator. Live Panel/browser acceptance and a backup/restore recovery drill remain outstanding.
- Privacy-safe diagnostics are implemented in `main`: structured redacted logs, bounded rotating storage, admin-only read-only health checks and a downloadable support bundle that excludes prompts, replies, memories, documents, credentials and free-form log messages. Live Panel/browser acceptance remains outstanding.
- Welsh/English support is implemented in `main`: per-user automatic/English/Welsh preference, language-aware prompts, schema migration, UI wiring, Welsh-sensitive-memory checks and a local model evaluation guide. The dependency-free, loopback-only Ollama benchmark runner is available at `scripts/benchmark_languages.py`; the selected local model has not yet been evaluated, so no language-quality claim is made. Voice recognition and speech output remain separate future work.
- Automatic migration recovery: when an existing database migration or its post-migration integrity checks fail, the CLI attempts to restore the verified pre-migration backup; a regression test covers the failure path.
- Automated Python tests, frontend JavaScript syntax validation and dependency vulnerability audit.
- Egg/runtime consistency regression checks: active Egg environment variables must be referenced by runtime code, and install-script persistent paths must match the model and database storage roots.
- Configurable per-user/shared document count and byte quotas, application declared-body limits, and per-user chat submission throttling; reverse-proxy enforcement is documented but not deployed.
- Bounded in-flight chat admission (one active generation plus up to eight additional requests by default); overload is rejected with HTTP 503 instead of accumulating an unbounded queue.
- Configurable per-user personal-memory count cap (100 by default), with atomic quota enforcement and graceful automatic-extraction behaviour when full.
- Network deployment design for Caddy public TLS, Nginx loopback edge limits, HTTPS public-IP access and private Tailscale Serve; Uvicorn forwarded-header trust is disabled by default.

The latest `main` merge is `62663ad` (PR #34, streamed request-body limit hardening). Python CI [#1179](https://github.com/lcswolf/orinoco-ai/actions/runs/46048840316) passed on the merge commit, including runtime and development dependency audits, frontend syntax validation, Python compilation and 330 tests. Container build/smoke [#555](https://github.com/lcswolf/orinoco-ai/actions/runs/46048840341) also passed on this commit; it built and tested the image without publishing it. GitHub CodeQL default setup completed analysis run [#6](https://github.com/lcswolf/orinoco-ai/actions/runs/46048839828) on this commit for Python, GitHub Actions and JavaScript/TypeScript. The repository alert inventory has not yet been independently reviewed, so this does not assert that there are no findings. The local Welsh/English model-quality benchmark has not yet been run. The published GHCR test image may lag behind `main`; anonymous/public pull access and live Panel import remain unverified.

- GPU detection, memory-based model-fit recommendations and performance history remain future resource-awareness work. The current implementation detects CPU and memory limits and adapts inference thread selection; it does not automatically select a model or context length based on RAM.
- The Orinoco-managed automatic backup scheduler is intended to be optional and disabled by default; Pterodactyl's own backup system remains a valid primary backup mechanism.

## Confirmed direction

- Self-hosted assistant named Orinoco.
- Fully custom Orinoco web interface; Open WebUI will not be used as the main frontend.
- Accessible mobile navigation drawer with keyboard focus management, Escape dismissal, inert background and compact narrow-screen topbar; real-device browser checks remain outstanding.
- Local model inference; no external AI inference API is intended.
- Ollama is the inference runtime, currently pinned to version 0.40.18 in the image.
- Initial target is a modest Ubuntu 24.04 LTS VPS.
- Pterodactyl Panel 1.13.0 (stable 1.x release line) is the target deployment manager.
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
- Anonymous GHCR pull verification, live Egg import and Pterodactyl node deployment.
- Host-level Caddy/Nginx configuration, firewall rules, certificate issuance/renewal and Tailscale Serve are documented but not applied or tested on the Leaseweb VPS.
- Production security review, MFA, live trusted-proxy configuration, chat retention and multi-worker quota coordination. Panel-triggered password recovery is implemented in `main` but still needs live Panel and browser verification.

## Next implementation sequence

0. Complete the Panel-first management release gate: first-admin setup, one-time administrator recovery, browser-only backup-key generation and the Panel Startup Command runbook audit are implemented in `main`. Verify the full workflow on a disposable Panel 1.13.0 server, including real-browser secret clearing and a restore/rollback drill. Track acceptance in [Panel-first Management](PANEL_MANAGEMENT.md).


1. Run the documented Welsh/English quality benchmark against the chosen local Ollama model before finalising the default. The language preference, prompt, UI, schema migration and Welsh privacy checks are implemented; live model quality and real-browser verification remain outstanding. Track acceptance in [Language Support](LANGUAGE_SUPPORT.md) and [issue #7](https://github.com/lcswolf/orinoco-ai/issues/7).
2. Extend resource-awareness only after measuring model fit and inference performance; do not automatically change the selected model or context until measurements justify it.
3. Keep the fixed Debian snapshot timestamp explicit and update it deliberately during security maintenance, then rerun container build and smoke checks.
4. Apply the Caddy/Nginx network design on the actual Leaseweb VPS, including Docker/Wings firewall rules, subdomain and IP certificate issuance, edge limits and private Tailscale Serve.
5. Validate the Egg on a disposable server in Panel 1.13.0 and test the proxy-to-allocation path.
6. Perform a real encrypted backup/restore and update/rollback drill on the disposable Pterodactyl server.
7. Browser-test the mobile navigation, narrow-screen layout and account settings on iOS, Android and desktop.
8. Publish a versioned stable image only after the live deployment and recovery release gates pass; Discord and voice follow later.

## Resource assumptions

The previously discussed target VPS has 4 vCPU and 6 GiB RAM. The proposed initial container allowance is approximately 4 GiB RAM, with one model generation at a time. These are planning values, not validated minimum requirements. Automatic memory extraction uses a second local model request after a chat reply, so it increases response time and can be disabled with AUTO_SAVE_MEMORIES=false.

## Release policy

The intended update channel is stable. Releases should be versioned, documented and tested. Database migrations must be backed up and have a documented recovery path.

## Next deployment-readiness gate

A disposable live-test runbook is prepared at [docs/PTERODACTYL_TEST_PLAN.md](PTERODACTYL_TEST_PLAN.md). It covers the Panel 1.13.0 import, Wings lifecycle, direct IP-and-port access, model startup, persistent data, account isolation, encrypted backup/restore, migration rollback, reverse proxy/TLS and Tailscale. A test image has been published, but anonymous GHCR pull verification and live Panel/VPS testing have not yet been completed. Python runtime and development dependencies are hash-locked, verified by clean hash-required installs and a clean vulnerability audit. Container build and smoke checks have passed on the latest merged main commit recorded above; each merge must continue to receive fresh main-branch checks.
