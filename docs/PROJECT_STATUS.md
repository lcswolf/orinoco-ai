# Project Status

**Overall status: early implementation — supervised Ollama runtime, readiness checks and Pterodactyl Egg preview committed.**

This page separates confirmed project decisions from implementation work. A planned feature is not considered implemented until code, tests and documentation exist.

## Implemented in the repository

- Public project repository and project documentation.
- Minimal FastAPI application with root and `/healthz` liveness endpoints.
- `/readyz` readiness endpoint that checks the local Ollama API and selected model.
- Automated tests for the API, Egg definition and runtime layout.
- Python dependency manifests for runtime and development.
- Pterodactyl-compatible Docker image foundation using a non-root `container` user and `/home/container` working directory.
- Pterodactyl startup entrypoint that expands simple uppercase `{{VARIABLE}}` placeholders without evaluating shell commands.
- Supervisor configuration for the web app, Ollama and first-run model initialisation in one container.
- Pinned Ollama CPU runtime installation, loopback-only API binding and model concurrency limits.
- First-run model download into persistent Pterodactyl server storage.
- Preview Pterodactyl 1.x Egg definition for Panel 1.13.0 and an install script that prepares persistent data folders.
- GitHub Actions workflows for Python tests and Docker image build validation.

The initial application and Egg tests passed in GitHub Actions. The original lightweight Docker image build passed. The expanded image including Ollama is being validated now; it has not yet been published to GHCR or tested on a live Pterodactyl node.

## Confirmed direction

- Self-hosted assistant named Orinoco.
- Local model inference; no external AI inference API is intended.
- Ollama is the inference runtime, currently pinned to stable version 0.40.18 in the image.
- Initial target is a modest Ubuntu 24.04 LTS VPS.
- Pterodactyl Panel 1.13.0 is the target deployment manager, using a custom Orinoco Egg and image.
- Stable releases are preferred for updates.
- Curated model list: Qwen 2.5 0.5B, 1.5B and 3B; 1.5B is the default.
- Initial context target is 2048 tokens and one model request at a time.
- Discord text integration is planned; voice listening must require explicit activation.
- User memories, chats and private documents must be isolated per account.
- Public registration should be disabled by default.
- Web research and user-provided URL summaries are planned optional features.

## Not implemented yet

- Chat interface and chat orchestration connected to Ollama.
- User authentication, roles and account management.
- Database, conversation storage and per-user memory controls.
- Document ingestion, retrieval and shared/private libraries.
- Web search and safe URL fetching.
- Discord integration and voice features.
- Production-ready Orinoco runtime image, published GHCR package and automated image release pipeline.
- Live import and test of the Egg against the user's Panel/Wings installation.
- Backup, restore, update and rollback tooling.
- Production security review and deployment.

## Suggested implementation sequence

1. Finish the expanded Docker build and runtime checks.
2. Add a minimal local chat endpoint with strict input validation and request limits.
3. Add the database, authentication, roles and isolated chat storage before exposing chat to users.
4. Add per-user memory review and document retrieval.
5. Add optional web search and safe URL summarisation.
6. Add backup, restore, health checks and update/rollback procedures.
7. Add Discord text integration; consider voice only after the core is stable.
8. Publish the stable image and import/test the finished Egg on the user's Panel before production deployment.

## Resource assumptions

The previously discussed target VPS has 4 vCPU and 6 GiB RAM. The proposed initial container allowance is approximately 4 GiB RAM, with one model generation at a time. These are planning values, not validated minimum requirements. The 3B model is experimental on this hardware; measure actual RAM use and response speed before making it a default.

## Release policy

The intended update channel is stable. Releases should be versioned, documented and tested. Database migrations must be backed up and have a documented recovery path.
