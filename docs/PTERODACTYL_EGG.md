# Pterodactyl Egg (Panel 1.x)

**Status: preview definition. Do not deploy yet.**

This Egg targets the legacy Pterodactyl 1.x import format and is intended for Panel 1.13.0. It remains a preview because the expanded Orinoco runtime image is still being built and tested; it has not yet been published to GHCR or imported into a live Panel.

## Files

- `egg/egg-orinoco.json` — importable PTDL_v1 Egg definition.
- `docker/Dockerfile` — custom runtime image, including the pinned Ollama release.
- `docker/supervisord.conf` — supervises the web app, Ollama, first-run model download and daily backup scheduler.
- `docker/ollama-start.sh` — starts Ollama bound only to loopback.
- `docker/model-init.sh` — downloads the selected model into persistent server storage when enabled.
- `docker/web-start.sh` — starts the web app on the primary Pterodactyl allocation.
- `orinoco/backups.py` — encrypted backup, restore and S3-compatible upload commands.

The planned image name is `ghcr.io/lcswolf/orinoco-ai:stable`.

## Runtime layout

Supervisor runs Ollama on `127.0.0.1:11434`, first-run model initialisation and the Orinoco web app on the assigned Pterodactyl allocation. The Ollama API is not exposed as a public allocation. Model files, the SQLite database, session secret, uploaded documents and extracted document index live in persistent server storage under `/home/container/data`.

The image pins Ollama 0.40.18, disables Ollama cloud features and limits model concurrency to one. The web app uses secure signed sessions, CSRF-protected authentication, per-user chat/memory/document isolation and administrator-managed accounts.

## Current capabilities

- Custom responsive Orinoco interface and sign-in.
- Local Ollama chat with private per-user conversation history.
- Argon2 accounts, administrator user management and password changes.
- Per-user automatic memories with review/edit/delete controls.
- Private and shared document libraries for TXT, Markdown, PDF, DOCX, XLSX and PPTX, with bounded extraction and FTS5 keyword retrieval.
- Explicit web-search workspace and per-message opt-in chat search using a configured SearXNG service.
- Encrypted local backup creation, verification and confirmed restore.
- S3-compatible off-site upload with remote object byte verification.
- Liveness endpoint `/healthz` and model readiness endpoint `/readyz`.

User-triggered public webpage fetching and local summarisation are implemented with DNS-pinned public-IP resolution and redirect checks. Discord and voice are still under development. The SearXNG feature requires the administrator to configure `SEARXNG_URL` and enable `ENABLE_WEB_SEARCH`. Search queries are sent to that configured service and its upstream providers. The chat search toggle is off by default for each message.

## Egg variables and security

The Egg includes curated model selection, automatic model download, model context, single-request concurrency, automatic memory saving, database path, optional integration settings, an admin-only backup encryption key, hidden S3-compatible destination/credential variables, a daily backup time and a local retention period. The defaults are 03:00 in the configured TIMEZONE and 14 days. The backup scheduler reports failures in the Pterodactyl console and writes non-secret operational status to `/home/container/data/backups/.scheduler-status.json`. Generate the backup key and store it securely outside the VPS. Configure a private bucket and a dedicated restricted credential; all S3 endpoints must use HTTPS. Remote object retention still needs a bucket lifecycle policy.

Keep the Discord token blank until its integration and secret-handling design are complete. A hidden Egg variable is not a secret store; processes inside the container can read environment variables. Never commit tokens or private data.

## Import steps (only after the image is published)

1. In the Panel, open **Admin → Nests**.
2. Create a dedicated Nest named **Orinoco AI**.
3. Choose **Import Egg** and select `egg/egg-orinoco.json`.
4. Add the tag `ai-assistant` if desired.
5. Do not create a server from this Egg until the image is published and the image pull/start test has passed.

The Egg uses `meta.version: PTDL_v1` for Panel 1.x compatibility. Tags are separate Panel objects and are not part of the Egg JSON.

## Resource and network notes

Use one assigned allocation for the web interface. Ollama and the SQLite database must remain internal. The earlier plan to allow around 4 GiB RAM to the container is a planning value, not a validated minimum. Measure memory use after the first real model test. The 3B model is experimental on the proposed 6 GiB VPS.

## Important security note

The session-signing secret, database, uploaded documents and extracted text are private persistent data and must be included in encrypted off-server backups. Never expose the `data` directory through the web server.
