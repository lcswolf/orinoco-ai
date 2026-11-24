# Pterodactyl Egg (Panel 1.x)

**Status: preview definition. Do not deploy yet.**

This Egg targets the legacy Pterodactyl 1.x import format and is intended for Panel 1.13.0. It is deliberately marked as a preview because the expanded Orinoco runtime image is being built and tested; it has not yet been published to GHCR or imported into a live Panel.

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

Model files are stored under `/home/container/data/models`, which is part of the persistent Pterodactyl server directory. Recreating the container should not require downloading the model again, provided the server files are retained.

The image pins Ollama to version `0.40.18` for repeatable builds. It disables Ollama cloud features and limits model concurrency to one, matching the initial low-memory VPS plan.

## Current application limitations

The current Orinoco Python app still exposes only its initial FastAPI status/health endpoints. The image now includes Ollama and can prepare the selected model, but **there is not yet a chat interface or application-to-Ollama chat integration**.

Authentication, per-user accounts, conversations, memory, document handling, search, Discord and voice are still under development. The Egg includes future settings for these features; settings that are described as planned do not activate those features yet.

- Do not add a real Discord token yet.
- Model selection and automatic download are implemented by the runtime bootstrap; the web app does not yet use the model for chat.
- `/healthz` only confirms that the web process is responding; it does not prove that the model download or other integrations are healthy.

## Import steps (only after the image is published)

1. In the Panel, open **Admin → Nests**.
2. Create a dedicated Nest named **Orinoco AI** (do not modify an existing Nest).
3. Open that Nest and choose **Import Egg**.
4. Select `egg/egg-orinoco.json`.
5. Add a tag named **Orinoco AI** with slug `ai-assistant`, if desired.
6. Do not create a server from this Egg until the image is published and the image pull/start test has passed.

The Egg uses the legacy `images` array and `meta.version: PTDL_v1` for compatibility with the Panel 1.x importer. Tags are a separate Panel object and are not included in the Egg JSON.

## Resource and network notes

Use one assigned allocation for the web interface. Ollama and any future database must remain internal and must not receive public allocations.

The earlier plan to allow around 4 GiB RAM to the container is still only a planning figure. Ollama's actual memory use depends on the selected model and context length; measure it after the first real model test before production use. The 3B option is experimental on the planned 6 GiB VPS.

## Important security note

A hidden Egg variable is not a secure secret store: processes inside the container can read environment variables. Keep the Discord token blank until dedicated secret handling is implemented, and never paste secrets into GitHub or issue logs.
