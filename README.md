# Orinoco AI

A self-hosted personal AI assistant with local inference, persistent memory, Discord integration and web research.

> **Project status: early implementation.** The custom interface, local model runtime and first authentication milestone are in place; Orinoco is not yet a complete assistant.

## Project goals

Orinoco aims to provide a friendly, private assistant that can be hosted on a modest VPS and use locally-run language models.

Planned capabilities include:

- A custom Orinoco web interface, built for this project rather than based on Open WebUI.
- Local model inference through Ollama, without relying on external AI inference APIs.
- Private administrator and standard-user accounts.
- Per-user chat history and personal memories, with controls to review, correct and delete memories.
- Private user documents and an administrator-managed shared knowledge library.
- Optional web research and summaries of user-provided URLs, with source links.
- Optional Discord text integration, with per-channel participation settings.
- Voice features that only listen when explicitly activated.
- Backups, health monitoring and administrator-managed model updates.

## Design principles

- **Privacy by default:** user conversations, documents and memories must remain separated.
- **Local inference:** prompts are processed by a model hosted alongside Orinoco.
- **Safe web access:** retrieved webpages are untrusted input and must not override system or user instructions.
- **Small-server friendly:** resource usage and model choices should suit modest VPS hardware.
- **Transparent operation:** distinguish verified information from uncertainty and provide source links where applicable.

## Planned deployment

The initial deployment is intended for Ubuntu 24.04 LTS on a rented VPS, with Pterodactyl Panel 1.13.0 managing Orinoco through a custom Egg and Docker image. The container foundation includes a pinned Ollama CPU runtime, a supervisor, first-run model download and separate liveness/readiness checks.

## Repository status

The repository includes a custom responsive interface, sign-in dialog, CSRF-protected login/logout API, signed secure sessions, SQLite account storage, Argon2 password hashing, a local administrator bootstrap command, authenticated chat, per-user saved conversations, FastAPI liveness/readiness endpoints, tests and a supervised Ollama runtime.

User-management screens, per-user memories, documents, Discord and search are not implemented yet. The expanded Docker image has not yet been published to GHCR or deployed.

See [Project Status](docs/PROJECT_STATUS.md), [Architecture](docs/ARCHITECTURE.md), [Development](docs/DEVELOPMENT.md) and [Pterodactyl Egg notes](docs/PTERODACTYL_EGG.md).

## Security

Do not commit passwords, tokens, API keys, private conversations, personal memories, uploaded documents, databases, backups or encryption keys. Ollama is configured for loopback-only access and cloud features are disabled. A hidden Pterodactyl variable is not a secure secret store. See [SECURITY.md](SECURITY.md) for reporting vulnerabilities.

## Contributing

Contributions and suggestions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

## Licence

This project is intended to be released under the MIT Licence. See [LICENSE](LICENSE).
