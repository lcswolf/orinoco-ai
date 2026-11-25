# Pterodactyl Egg (Panel 1.x / 1.13.0)

For the full installation, configuration and user walkthrough, see the [User and Setup Guide](USER_GUIDE.md). The [Panel-first Management requirements](PANEL_MANAGEMENT.md) define the operational target and outstanding work.

**Status: preview definition. Do not deploy yet.**

This Egg targets the stable Pterodactyl 1.x import format (`PTDL_v1`) and the confirmed Panel 1.13.0 target. It remains a preview: import compatibility and runtime behaviour have not yet been validated on a live Panel, and the matching Orinoco image has not been published to GHCR.

## Files

- `egg/egg-orinoco.json` — importable PTDL_v1 Egg definition.
- `docker/Dockerfile` — custom runtime image, including the pinned Ollama release.
- `docker/supervisord.conf` — supervises the web app, Ollama, first-run model download and daily backup scheduler.
- `docker/ollama-start.sh` — starts Ollama bound only to loopback.
- `docker/model-init.sh` — downloads the selected model into persistent server storage when enabled.
- `docker/web-start.sh` — starts the web app on the primary Pterodactyl allocation.
- `orinoco/backups.py` — encrypted backup, restore and S3-compatible upload commands.

The planned image name is `ghcr.io/lcswolf/orinoco-ai:stable`. See [Updating and Rollback](UPDATING.md) for the one-shot Pterodactyl startup-command procedure for manual backups and restore.

## Runtime layout

Supervisor runs Ollama on `127.0.0.1:11434`, first-run model initialisation and the Orinoco web app on the assigned Pterodactyl allocation. The Ollama API is not exposed as a public allocation. Model files, the SQLite database, session secret, uploaded documents and extracted document index live in persistent server storage under `/home/container/data`.

The image pins Ollama 0.40.18, disables Ollama cloud features and limits model concurrency to one. The web app uses secure signed sessions, CSRF-protected authentication, per-user chat/memory/document isolation and administrator-managed accounts. **Panel-first status:** a token-gated first-run administrator setup page and API are implemented on the feature branch. They use a hidden Egg variable, CSRF protection, constant-time token comparison, attempt throttling, a 30-minute validity window after application start and an atomic one-time database guard. CI and live Panel verification are still pending. Panel-triggered administrator recovery is also implemented on the feature branch: its token expires 30 minutes after startup, a consumed token fingerprint is stored durably, and password reset revokes existing sessions. CI and live Panel verification remain outstanding, so Panel-first management is not yet complete. See [Panel-first Management](PANEL_MANAGEMENT.md).

The initial chat queue admits one active generation plus up to eight additional in-flight chat requests by default. Excess requests receive HTTP 503 with a short retry hint instead of accumulating without bound. The administrator can adjust `ORINOCO_MAX_PENDING_GENERATIONS` from 0 to 32 in the Egg; this queue and the per-user chat rate limiter are process-local and assume one web worker.

Personal memories are capped at 100 per account by default. The administrator can adjust `ORINOCO_MAX_MEMORIES_PER_USER` from 1 to 1000 in the Egg; manual and automatically extracted memories share this allowance.

## Current capabilities

- Custom responsive Orinoco interface and sign-in.
- Local Ollama chat with private per-user conversation history.
- Argon2 accounts, administrator user management, password changes, a token-gated first-run web bootstrap (feature branch; verification pending) and an offline TTY-only password-reset command.
- Per-user automatic memories with review/edit/delete controls.
- Private and shared document libraries for TXT, Markdown, PDF, DOCX, XLSX and PPTX, with bounded extraction and FTS5 keyword retrieval.
- Explicit web-search workspace and per-message opt-in chat search using a configured SearXNG service.
- Encrypted local backup creation, verification and confirmed restore.
- S3-compatible off-site upload with remote object byte verification.
- Liveness endpoint `/healthz` and model readiness endpoint `/readyz`.

User-triggered public webpage fetching and local summarisation are implemented with DNS-pinned public-IP resolution and redirect checks. Discord and voice are still under development. The SearXNG feature requires the administrator to configure `SEARXNG_URL` and enable `ENABLE_WEB_SEARCH`. Search queries are sent to that configured service and its upstream providers. The chat search toggle is off by default for each message.

## Egg variables and security

The Egg includes curated model selection, automatic model download, model context, single-request concurrency, automatic memory saving, database path, a hidden one-time first-administrator setup token, an administrator-only trusted-proxy allowlist, optional integration settings, an admin-only backup encryption key, hidden S3-compatible destination/credential variables, a daily backup time and a local retention period. The defaults are 03:00 in the configured TIMEZONE and 14 days. The backup encryption key is a required, hidden, administrator-supplied value when creating the Pterodactyl server. The current CLI key generator prints to standard output; a safe Panel-first generation workflow that avoids persistent console logs remains outstanding. The `SEARXNG_URL` endpoint is also hidden and administrator-only because it controls an outbound network destination. The backup scheduler reports failures in the Pterodactyl console and writes non-secret operational status to `/home/container/data/backups/.scheduler-status.json`. Configure a private bucket and a dedicated restricted credential; all S3 endpoints must use HTTPS. Remote object retention still needs a bucket lifecycle policy.

Keep the Discord token blank until its integration and secret-handling design are complete. A hidden Egg variable is not a secret store; processes inside the container can read environment variables. Never commit tokens or private data.

## Import steps (only after the image is published)

1. In the Panel, open **Admin → Nests**.
2. Create a dedicated Nest named **Orinoco AI**.
3. Choose **Import Egg** and select `egg/egg-orinoco.json`.
4. Add the tag `ai-assistant` if desired.
5. Do not create a server from this Egg until the image is published and the image pull/start test has passed.

The Egg uses `meta.version: PTDL_v1` for Panel 1.x compatibility. Tags are separate Panel objects and are not part of the Egg JSON.

## Reverse proxy and access paths

The Egg/container web process listens on its assigned Pterodactyl allocation. In the planned host topology, Caddy terminates public HTTPS and proxies to a loopback-only Nginx edge listener, which applies request-size and per-client rate/connection limits before proxying to that allocation. Do not expose the allocation directly to the internet. Ollama remains loopback-only inside the container.

The intended public URLs are the configured HTTPS subdomain and `https://PUBLIC_IPV4:8443/`. Private access uses Tailscale Serve on HTTPS port 8444 and is restricted by tailnet access-control policy; do not use Funnel. See [Network Deployment](NETWORK_DEPLOYMENT.md) for the Caddy/Nginx templates, firewall boundaries and live verification checklist.

The container explicitly starts Uvicorn with `--no-proxy-headers`. Do not enable forwarded-header trust or use a wildcard trusted-proxy list. If forwarded headers are ever required, first measure the proxy peer address from inside the container and allow-list only that exact peer/subnet.

## Resource and network notes

Use one assigned allocation for the web interface. Ollama and the SQLite database must remain internal. The earlier plan to allow around 4 GiB RAM to the container is a planning value, not a validated minimum. Measure memory use after the first real model test. The 3B model is experimental on the proposed 6 GiB VPS.

## Important security note

The session-signing secret, database, uploaded documents and extracted text are private persistent data and must be included in encrypted off-server backups. Never expose the `data` directory through the web server.
