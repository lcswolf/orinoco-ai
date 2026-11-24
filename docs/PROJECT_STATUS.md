# Project Status

**Overall status: early implementation — foundation scaffold committed.**

This page separates confirmed project decisions from implementation work. A planned feature is not considered implemented until code, tests and documentation exist.

## Implemented in the repository

- Public project repository and initial project documentation.
- Minimal FastAPI application package.
- Root information endpoint and `/healthz` health endpoint.
- Initial automated tests for the endpoints.
- Python dependency manifests for runtime and development.
- Docker image foundation targeting Pterodactyl's container conventions.
- Startup entrypoint that expands simple uppercase `{{VARIABLE}}` placeholders without evaluating a shell command.
- Local development and container build instructions.

The initial tests were run in the development environment and passed (2 tests). The Docker image has not yet been built or tested in Docker.

## Confirmed direction

- Self-hosted assistant named Orinoco.
- Local model inference; no external AI inference API is intended.
- Ollama is the planned inference runtime.
- Initial target is a modest Ubuntu 24.04 LTS VPS.
- Pterodactyl is the planned deployment manager, using a custom Orinoco Egg and image.
- Stable releases are preferred for updates.
- The initial model choice is a curated list, with Qwen 2.5 1.5B Q4 proposed as the default.
- Discord text integration is planned; voice listening must require explicit activation.
- User memories, chats and private documents must be isolated per account.
- Public registration should be disabled by default.
- Web research and user-provided URL summaries are planned optional features.

## Not implemented yet

- User interface, authentication, roles and account management.
- Chat orchestration, chat storage and per-user memory controls.
- Database and document ingestion/retrieval.
- Ollama process management, model selection and model downloads.
- Web search and safe URL fetching.
- Discord integration and voice features.
- Production-ready Pterodactyl Egg and installation script.
- Published GHCR image, automated image build/release pipeline.
- Backup, restore, update and rollback tooling.
- Production security review and deployment.

## Suggested implementation sequence

1. Stabilise the application/container foundation and add CI validation.
2. Design the data model and security boundaries.
3. Add a minimal chat flow connected to local Ollama.
4. Add authentication, roles and isolated chat storage.
5. Add memory review and user document retrieval.
6. Add optional web search and safe URL summarisation.
7. Finalise and test the Pterodactyl Egg against the exact installed Panel/Wings version.
8. Add backup, restore, health checks and update/rollback procedures.
9. Add Discord text integration; consider voice only after the core is stable.

## Resource assumptions

The previously discussed target VPS has 4 vCPU and 6 GiB RAM. The proposed initial container allowance is approximately 4 GiB RAM, with one model generation at a time. These are planning values, not validated minimum requirements. Measure actual use before production deployment.

## Release policy

The intended update channel is stable. Releases should be versioned, documented and tested. Database migrations must be backed up and have a documented recovery path.
