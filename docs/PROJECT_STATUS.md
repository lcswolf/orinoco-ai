# Project Status

**Overall status: early implementation — custom interface, local model runtime, authentication, private chat and personal memory milestones committed.**

This page separates confirmed project decisions from implementation work. A planned feature is not considered implemented until code, tests and documentation exist.

## Implemented in the repository

- Public project repository and project documentation.
- Custom responsive Orinoco interface shell, served directly by FastAPI.
- Orinoco's requested greeting and an initial local-model status display.
- Custom sign-in dialog connected to the authentication API.
- Account settings dialog with password changes and an administrator-only user-management screen.
- Admin API to create standard accounts, list accounts and suspend/reactivate users; the last active administrator cannot be suspended.
- Working authenticated chat composer with saved conversation list, conversation switching and a mobile recent-chat selector.
- Local Ollama chat orchestration with one generation at a time, bounded response length and a short conversation context window.
- Atomic saving of user/assistant message pairs and server-side conversation ownership checks.
- Per-user personal memories with add, list, edit and delete controls.
- Automatic extraction of a small number of durable, non-sensitive personal memories after chat turns, with an Egg setting to disable it.
- Saved memories are included only in that account's future chat context; memory content is treated as reference data, not instructions.
- Conservative automatic-memory filters for passwords, secrets, contact details, precise addresses, postcodes and selected sensitive categories.
- Signed session cookies with secure, HTTP-only and SameSite=Lax settings.
- CSRF tokens for login and logout, plus session rotation after successful login.
- SQLite account, conversation and memory storage; Argon2 password hashing; username validation; local first-admin bootstrap command.
- A basic in-process throttle for repeated failed login attempts.
- /healthz liveness endpoint and /readyz readiness endpoint.
- Readiness check for the local Ollama API and selected model.
- Automated tests for the API, custom interface, authentication, account storage, chat, memory isolation and extraction, Egg definition and runtime layout.
- Python dependency manifests for runtime and development.
- Pterodactyl-compatible Docker image foundation using a non-root container user and /home/container working directory.
- Pterodactyl startup entrypoint that expands simple uppercase {{VARIABLE}} placeholders without evaluating shell commands.
- Supervisor configuration for the web app, Ollama and first-run model initialisation.
- Pinned Ollama CPU runtime installation, loopback-only API binding and model concurrency limits.
- First-run model download into persistent Pterodactyl server storage.
- Preview Pterodactyl 1.x Egg definition for Panel 1.13.0 and an install script that prepares persistent data folders.
- GitHub Actions workflows for Python tests and Docker image build validation.

The latest completed Python test run passed all 46 tests. The custom interface JavaScript syntax check also passes. The expanded image build and container runtime smoke test are still being validated. The image has not yet been published to GHCR or tested on a live Pterodactyl node.

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

- Conversation deletion/editing, pagination and streaming responses.
- Document ingestion, retrieval and shared/private libraries.
- Web search and safe URL fetching.
- Discord integration and voice features.
- Production-ready Orinoco runtime image, published GHCR package and automated image release pipeline.
- Live import and test of the Egg against the user's Panel/Wings installation.
- Backup, restore, update and rollback tooling.
- Production security review, MFA and account recovery.
- Server-side session revocation across all devices after password changes.

## Suggested implementation sequence

1. Finish frontend and container smoke tests.
2. Add document ingestion and shared/private knowledge libraries.
3. Add optional web research and safe URL summaries.
4. Add administrator settings, backups, restore and update/rollback procedures.
5. Add Discord text integration; consider voice only after the core is stable.
6. Publish the stable image and import/test the finished Egg on the user's Panel before production deployment.

## Resource assumptions

The previously discussed target VPS has 4 vCPU and 6 GiB RAM. The proposed initial container allowance is approximately 4 GiB RAM, with one model generation at a time. These are planning values, not validated minimum requirements. The 3B model is experimental on this hardware; measure actual RAM use and response speed before making it a default.

Automatic memory extraction uses a second local model request after a chat reply, so it increases response time. It can be disabled with AUTO_SAVE_MEMORIES=false. Users can review, correct and delete saved memories from their account settings.

## Release policy

The intended update channel is stable. Releases should be versioned, documented and tested. Database migrations must be backed up and have a documented recovery path.
