# Pterodactyl Egg (Panel 1.x)

**Status: preview definition. Do not deploy yet.**

This Egg targets the legacy Pterodactyl 1.x import format and is intended for the user's Panel 1.13.0. It is deliberately marked as a preview because the current Orinoco image has not yet been built or published to GHCR, and the application is still a FastAPI health-check scaffold.

## Files

- `egg/egg-orinoco.json` — importable PTDL_v1 Egg definition.
- Runtime image — planned as `ghcr.io/lcswolf/orinoco-ai:stable`.
- Runtime command — starts the FastAPI app on the primary Pterodactyl allocation.

## Import steps (when the image is ready)

1. In the Panel, open **Admin → Nests**.
2. Create a dedicated Nest named **Orinoco AI** (do not modify an existing Nest).
3. Open that Nest and choose **Import Egg**.
4. Select `egg/egg-orinoco.json`.
5. Add a tag named **Orinoco AI** with slug `ai-assistant`, if desired.
6. Do not create a server from this Egg until the image is published and the image pull/start test has passed.

The Egg uses the legacy `images` array and `meta.version: PTDL_v1` for compatibility with the Panel 1.x importer.

## Current limitations

The current image foundation only contains the FastAPI application scaffold and its `/healthz` endpoint. It does **not** yet include Ollama, model downloads, authentication, chat, memory, database, web search, Discord or voice.

The Egg exposes the agreed future settings so we can keep the deployment interface stable while those features are implemented. At this stage, most of those settings are placeholders and do not activate functionality. In particular:

- Do not add a real Discord token yet.
- Model selection and automatic download are not implemented yet.
- Search, Discord and voice toggles are not wired up yet.
- `/healthz` only confirms that the web process is responding; it does not prove that a model or integrations are healthy.

## Resource and network notes

Use one assigned allocation for the web interface. The application should bind to `0.0.0.0` and the supplied `SERVER_PORT`. Ollama and the database must remain internal and must not receive public allocations.

The intended first deployment is one Orinoco Egg/container with a modest resource cap, but the final memory and CPU limits must be validated after Ollama and the selected model are integrated. Do not assume the earlier 4 GiB container estimate is sufficient until measured.

## Important security note

A hidden Egg variable is not a secure secret store: processes inside the container can read environment variables. Keep the Discord token blank until dedicated secret handling is implemented, and never paste secrets into GitHub or issue logs.
