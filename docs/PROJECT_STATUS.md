# Project Status

**Overall status: early implementation — custom interface, local model runtime and first authentication milestone committed.**

This page separates confirmed project decisions from implementation work. A planned feature is not considered implemented until code, tests and documentation exist.

## Implemented in the repository

- Public project repository and project documentation.
- Custom responsive Orinoco interface shell, served directly by FastAPI.
- Orinoco's requested greeting and an initial local-model status display.
- Custom sign-in dialog connected to the authentication API.
- Working authenticated chat composer with saved conversation list, conversation switching and a mobile recent-chat selector.
- Local Ollama chat orchestration with one generation at a time, bounded response length and a short conversation context window.
- Atomic saving of user/assistant message pairs and server-side conversation ownership checks.
- Signed session cookies with secure, HTTP-only and SameSite=Lax settings.
- CSRF tokens for login and logout, plus session rotation after successful login.
- SQLite account storage, Argon2 password hashing, username validation and a local-only first-admin bootstrap command.
- A basic in-process throttle for repeated failed login attempts.
- /healthz liveness endpoint and /readyz readiness endpoint.
- Readiness check for the local Ollama API and selected model.
- Automated tests for the API, custom interface, authentication, account storage, session settings, Egg definition and runtime layout.
- Python dependency manifests for runtime and development.
- Pterodactyl-compatible Docker image foundation using a non-root container user and /home/container working directory.
- Pterodactyl startup entrypoint that expands simple uppercase {{VARIABLE}} placeholders without evaluating shell commands.
- Supervisor configuration for the web app, Ollama and first-run model initialisation.
- Pinned Ollama CPU runtime installation, loopback-only API binding and model concurrency limits.
- First-run model download into persistent Pterodactyl server storage.
- Preview Pterodactyl 1.x Egg definition for Panel 1.13.0 and an install script that prepares persistent data folders.
- GitHub Actions workflows for Python tests and Docker image build validation.

The latest completed GitHub Actions Python test run passed all 26 tests. The expanded image build and container runtime smoke test are still being validated. The image has not yet been published to GHCR or tested on a live Pterodactyl node.

## Confirmed direction

- Self-hosted assistant named Orinoco.
- Fully custom Orinoco web interface; Open WebUI will not be used as the main frontend.
- Local model inference; no external AI inference API is intended.
- Ollama is the inference runtime, currently pinned to stable version 0.40.18 in the image.
- Initial target is a modest Ubuntu 24.04 LTS VPS.
- Pterodactyl Panel 1.13.0 is the target deployment manager, using a custom Egg and image.
- Stable releases are preferred for updates.
- Curated model list: Qwen 2.5 0.5B, 1.5B and 3B; 1.5B is the default.
- Initial context target is 2048 tokens and one model request at a time.
- Discord text integration is planned; voice listening must require explicit activation.
- User memories, chats and private documents must be isolated per account.
- Public registration should be disabled by default.
- Web research and user-provided URL summaries are planned optional features.

## Not implemented yet

- User-management routes and administrator screens.
- Conversation deletion/editing, pagination and streaming responses.
- Per-user memory review and correction controls.
- Document ingestion, retrieval and shared/private libraries.
- Web search and safe URL fetching.
- Discord integration and voice features.
- Production-ready Orinoco runtime image, published GHCR package and automated image release pipeline.
- Live import and test of the Egg against the user's Panel/Wings installation.
- Backup, restore, update and rollback tooling.
- Production security review, MFA and account recovery.

## Suggested implementation sequence

1. Finish frontend and container smoke tests.
2. Add authenticated chat orchestration and per-user conversation storage.
3. Add user-management and administrator screens, then user preferences and memory controls.
4. Add document retrieval, optional web research and safe URL summaries.
5. Add administrator settings, backups, restore and update/rollback procedures.
6. Add Discord text integration; consider voice only after the core is stable.
7. Publish the stable image and import/test the finished Egg on the user's Panel before production deployment.

## Resource assumptions

The previously discussed target VPS has 4 vCPU and 6 GiB RAM. The proposed initial container allowance is approximately 4 GiB RAM, with one model generation at a time. These are planning values, not validated minimum requirements. The 3B model is experimental on this hardware; measure actual RAM use and response speed before making it a default.

## Release policy

The intended update channel is stable. Releases should be versioned, documented and tested. Database migrations must be backed up and have a documented recovery path.
