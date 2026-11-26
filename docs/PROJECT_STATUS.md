# Project Status

**Overall status: early implementation — custom interface, local model runtime, authentication, private chat, personal memory and document-library milestones committed.**

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
- Supervised daily encrypted backup scheduler (03:00 in the configured timezone by default), optional verified S3 upload, configurable 1–365 day local retention and persistent failure status.
- Session-secret symlink rejection and restrictive file permissions; safe backup restore recovery-path checks.
- CI dependency vulnerability audit and weekly Dependabot monitoring for Python packages and GitHub Actions. GitHub Actions are pinned to immutable commit SHAs; Python runtime and development dependencies are now compiled into SHA-256 hash-locked requirements files; CI and the Docker image install them with `--require-hashes`.
- Operator runbook for manual image updates, one-shot backup/restore commands and rollback sequencing; backup-verified update preparation and explicit SQLite migration CLI.
- Panel-first administrator setup and recovery on the draft feature branch: token-gated first-admin creation, expiring one-time recovery with session revocation, and a browser-only backup-key generator. Python CI #1022 passed 259 tests and container build/smoke #429 passed; live Panel/browser checks are still outstanding.
- Welsh/English support is tracked in [issue #7](https://github.com/lcswolf/orinoco-ai/issues/7) and implemented on `feature/welsh-english-language-support`: per-user automatic/English/Welsh preference, language-aware prompts, schema-v9 migration, UI wiring, Welsh-sensitive-memory checks and a local model evaluation guide. Python CI [#1038](https://github.com/lcswolf/orinoco-ai/actions/runs/45728601181) passed **261 tests**, dependency audit and frontend JavaScript syntax. Container build/smoke [#446](https://github.com/lcswolf/orinoco-ai/actions/runs/45728601173) is still completing. The selected Ollama model has not yet been run through the bilingual quality benchmark, so no language-quality claim is made.
- Automatic migration recovery: when an existing database migration or its post-migration integrity checks fail, the CLI attempts to restore the verified pre-migration backup; a regression test covers the failure path.
- Automated Python tests, frontend JavaScript syntax validation and dependency vulnerability audit.
- Egg/runtime consistency regression checks: active Egg environment variables must be referenced by runtime code, and install-script persistent paths must match the model and database storage roots.
- Configurable per-user/shared document count and byte quotas, application declared-body limits, and per-user chat submission throttling; reverse-proxy enforcement is documented but not deployed.
- Bounded in-flight chat admission (one active generation plus up to eight additional requests by default); overload is rejected with HTTP 503 instead of accumulating an unbounded queue.
- Configurable per-user personal-memory count cap (100 by default), with atomic quota enforcement and graceful automatic-extraction behaviour when full.
- Network deployment design for Caddy public TLS, Nginx loopback edge limits, HTTPS public-IP access and private Tailscale Serve; Uvicorn forwarded-header trust is disabled by default.

The latest completed Python CI for the Panel-first feature branch [#1022](https://github.com/lcswolf/orinoco-ai/actions/runs/45707665093) passed: **259 tests passed**, the hash-locked dependency audit found no known vulnerabilities, and frontend JavaScript syntax validation passed. Container build and smoke test [#429](https://github.com/lcswolf/orinoco-ai/actions/runs/45707665035) also passed, including Egg JSON, proxy-template validation, image build, service startup and health checks. The image was not published. The user/setup guide and related documentation updates also passed the full CI workflow (#979–#984). Container build and smoke test [#399](https://github.com/lcswolf/orinoco-ai/actions/runs/45682975877) passed on commit `4024b3ce` with the base-image digest pinned and fixed Debian apt snapshot `20261125T000000Z`. Two known deprecation warnings remain: Starlette's `httpx`-backed test-client integration and the deprecated HTTP 422 constant. Neither warning caused a test failure. Python runtime and development dependency locks are hash-locked and installed with `--require-hashes`; the lock compiler is pinned to `pip-tools==7.7.0`. GitHub Actions use immutable SHA pins and weekly Dependabot monitoring remains enabled. The repository-level reviews cover authentication/session handling, document ownership and extraction, database query ownership and transaction boundaries, additive schema upgrades, encrypted backup archive validation, WAL-consistent snapshots, restore rollback and remote S3 byte verification, plus the Pterodactyl Egg and container startup/runtime configuration. Frontend source checks cover keyboard navigation, accessible labels, safe text rendering and responsive layout rules; real-device browser checks remain outstanding. The image remains unpublished and has not been imported into a live Pterodactyl Panel.

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
- Production-ready image publication, live Egg import and Pterodactyl node deployment.
- Host-level Caddy/Nginx configuration, firewall rules, certificate issuance/renewal and Tailscale Serve are documented but not applied or tested on the Leaseweb VPS.
- Production security review, MFA, live trusted-proxy configuration, chat retention and multi-worker quota coordination. Panel-triggered password recovery is implemented on the feature branch but still needs live Panel and browser verification.

## Next implementation sequence

0. Complete the Panel-first management release gate: first-admin setup, one-time administrator recovery, browser-only backup-key generation and the Panel Startup Command runbook audit are implemented on the feature branch. Python CI #1022 (259 tests) and container smoke #429 passed. Verify the full workflow on a disposable Panel 1.13.0 server, including real-browser secret clearing and a restore/rollback drill. Track acceptance in [Panel-first Management](PANEL_MANAGEMENT.md).


1. Run the documented Welsh/English quality benchmark against the chosen local Ollama model before finalising the default. The language preference, prompt, UI, schema migration, Welsh privacy checks and 261 automated tests have passed; live model quality and real-browser verification remain outstanding. Track acceptance in [Language Support](LANGUAGE_SUPPORT.md) and [issue #7](https://github.com/lcswolf/orinoco-ai/issues/7).
2. Keep the fixed Debian snapshot timestamp explicit and update it deliberately during security maintenance, then rerun container build and smoke checks.
3. Apply the Caddy/Nginx network design on the actual Leaseweb VPS, including Docker/Wings firewall rules, subdomain and IP certificate issuance, edge limits and private Tailscale Serve.
4. Validate the Egg on a disposable server in Panel 1.13.0 and test the proxy-to-allocation path.
5. Perform a real encrypted backup/restore and update/rollback drill on the disposable Pterodactyl server.
6. Browser-test the mobile navigation, narrow-screen layout and account settings on iOS, Android and desktop.
7. Publish a versioned stable image only after the live deployment and recovery release gates pass; Discord and voice follow later.

## Resource assumptions

The previously discussed target VPS has 4 vCPU and 6 GiB RAM. The proposed initial container allowance is approximately 4 GiB RAM, with one model generation at a time. These are planning values, not validated minimum requirements. Automatic memory extraction uses a second local model request after a chat reply, so it increases response time and can be disabled with AUTO_SAVE_MEMORIES=false.

## Release policy

The intended update channel is stable. Releases should be versioned, documented and tested. Database migrations must be backed up and have a documented recovery path.

## Next deployment-readiness gate

A disposable live-test runbook is prepared at [docs/PTERODACTYL_TEST_PLAN.md](PTERODACTYL_TEST_PLAN.md). It covers the Panel 1.13.0 import, Wings lifecycle, direct IP-and-port access, model startup, persistent data, account isolation, encrypted backup/restore, migration rollback, reverse proxy/TLS and Tailscale. No image has been published and no live Panel/VPS test has been run. Python runtime and development dependencies are hash-locked, verified by clean hash-required installs and a clean vulnerability audit. The container smoke test passed on commit `9b0541ff` with the base-image digest pinned. The Debian snapshot source configuration passed container build and smoke run #399.
