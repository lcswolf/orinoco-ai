# Project Status

**Overall status: planning and repository scaffolding.**

This page separates confirmed project decisions from implementation work. A planned feature is not considered implemented until code, tests and documentation exist.

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

- Orinoco application and web interface.
- Authentication, roles and account management.
- Chat storage and per-user memory controls.
- Document ingestion and retrieval.
- Ollama integration and model management.
- Web search and URL fetching.
- Discord integration and voice features.
- Docker image, process supervision and Pterodactyl Egg.
- Installer, updater, backup and restore tooling.
- Automated tests and production deployment.

## Suggested implementation sequence

1. Define the application architecture, data model and security boundaries.
2. Build a minimal web application and local Ollama connection.
3. Add authentication, roles and isolated chat storage.
4. Add memory review and user document retrieval.
5. Add optional web search and safe URL summarisation.
6. Package the application in a non-root Docker image and create the Pterodactyl Egg.
7. Add backup, restore, health checks and update/rollback procedures.
8. Add Discord text integration; consider voice only after the core is stable.

## Resource assumptions

The previously discussed target VPS has 4 vCPU and 6 GiB RAM. The proposed initial container allowance is approximately 4 GiB RAM, with one model generation at a time. These are planning values, not validated minimum requirements. Measure actual use before production deployment.

## Release policy

The intended update channel is stable. Releases should be versioned, documented and tested. Database migrations must be backed up and have a documented recovery path.
