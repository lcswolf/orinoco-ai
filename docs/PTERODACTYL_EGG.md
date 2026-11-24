# Pterodactyl Egg (Panel 1.x)

**Status: preview definition. Do not deploy yet.**

This Egg targets the legacy Pterodactyl 1.x import format and is intended for Panel 1.13.0. It remains a preview because the expanded Orinoco runtime image is still being built and tested; it has not yet been published to GHCR or imported into a live Panel.

## Files

- `egg/egg-orinoco.json` — importable PTDL_v1 Egg definition.
- `docker/Dockerfile` — custom runtime image, including the pinned Ollama release.
- `docker/supervisord.conf` — supervises the web app, Ollama and first-run model download.
- `docker/ollama-start.sh` — starts Ollama bound only to loopback.
- `docker/model-init.sh` — downloads the selected model into persistent server storage when enabled.
- `docker/web-start.sh` — starts the web app on the primary Pterodactyl allocation.

The planned image name is `ghcr.io/lcswolf/orinoco-ai:stable`.

## How the single-container layout works

The Egg uses one Pterodactyl server/container. Supervisor runs three processes:

1. **Ollama** — local CPU inference service, listening only on `127.0.0.1:11434`; it is not exposed through a Pterodactyl allocation.
2. **Model initialisation** — waits for Ollama and downloads the selected model if automatic download is enabled. It exits after the initial check/download.
3. **Orinoco web app** — binds to `0.0.0.0` and the server's assigned `SERVER_PORT`.

Model files are stored under `/home/container/data/models`, which is part of the persistent Pterodactyl server directory. The SQLite database and generated session-signing secret are stored under `/home/container/data`. Recreating the container should not require downloading the model again or resetting sessions, provided the server files are retained.

The image pins Ollama to version `0.40.18` for repeatable builds. It disables Ollama cloud features and limits model concurrency to one, matching the initial low-memory VPS plan.

## Current application capabilities

The current application foundation includes:

- Custom Orinoco web interface and sign-in dialog.
- SQLite user accounts with Argon2 password hashes.
- Secure signed sessions and CSRF-protected authentication.
- Administrator account creation, suspension and reactivation.
- Authenticated chat through the local Ollama service.
- Per-user saved conversation history with server-side ownership checks.
- Per-user memories, automatic extraction, and review/edit/delete controls.
- Private and shared document libraries for TXT, Markdown, PDF, DOCX, XLSX and PPTX, with bounded local text extraction and SQLite FTS5 retrieval.
- Liveness endpoint `/healthz` and model readiness endpoint `/readyz`.

Web search, Discord and voice are still under development. Document uploads and basic keyword retrieval are implemented; scanned-PDF OCR and advanced semantic search are not.

- Do not add a real Discord token yet.
- Automatic memory extraction uses an additional local model request after a chat reply. It can be disabled with `AUTO_SAVE_MEMORIES=false`.
- `/healthz` confirms that the web process is responding. `/readyz` checks that Ollama and the selected model are available.
- A hidden Egg variable is not a secure secret store; processes inside the container can read environment variables.

## Egg variables

The Egg includes the curated model selector, automatic model download, context length, single-request concurrency, automatic memory saving, database path and future integration settings.

The Discord token remains blank and non-editable. Do not paste secrets into GitHub or issue logs.

## Import steps (only after the image is published)

1. In the Panel, open **Admin → Nests**.
2. Create a dedicated Nest named **Orinoco AI** (do not modify an existing Nest).
3. Open that Nest and choose **Import Egg**.
4. Select `egg/egg-orinoco.json`.
5. Add a tag named **Orinoco AI** with slug `ai-assistant`, if desired.
6. Do not create a server from this Egg until the image is published and the image pull/start test has passed.

The Egg uses the legacy `images` array and `meta.version: PTDL_v1` for compatibility with the Panel 1.x importer. Tags are a separate Panel object and are not included in the Egg JSON.

## Resource and network notes

Use one assigned allocation for the web interface. Ollama and the database must remain internal and must not receive public allocations.

The earlier plan to allow around 4 GiB RAM to the container is still only a planning figure. Ollama's actual memory use depends on the selected model and context length; measure it after the first real model test before production use. The 3B option is experimental on the planned 6 GiB VPS.

## Important security note

Keep the Discord token blank until the integration and secret-handling design are complete. The session-signing secret and SQLite database are persistent private data and must be included in encrypted off-server backups. Never expose the `data` directory through the web server.
