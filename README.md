# Orinoco AI

A self-hosted personal AI assistant with local inference, persistent memory, Discord integration and web research.

> **Project status: early implementation.** The runtime foundation is taking shape, but Orinoco is not yet a usable assistant.

## Project goals

Orinoco aims to provide a friendly, private assistant that can be hosted on a modest VPS and use locally-run language models.

Planned capabilities include:

- Local model inference through Ollama, without relying on external AI inference APIs.
- A private web interface with administrator and standard-user accounts.
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

The initial deployment is intended for Ubuntu 24.04 LTS on a rented VPS, with Pterodactyl Panel 1.13.0 managing Orinoco through a custom Egg and Docker image. The container foundation now includes a pinned Ollama CPU runtime, a supervisor, first-run model download and separate liveness/readiness checks. The selected model files are intended to persist in the Pterodactyl server directory.

## Repository status

The repository includes a FastAPI foundation, liveness/readiness endpoints, tests, a supervised Ollama runtime and a **preview Pterodactyl 1.x Egg**. The app can check that Ollama and the selected model are available, but it does not yet provide chat, authentication, a database, user memories, Discord or search. The expanded Docker image is being validated and has not yet been published to GHCR or deployed.

See [Project Status](docs/PROJECT_STATUS.md), [Architecture](docs/ARCHITECTURE.md), [Development](docs/DEVELOPMENT.md) and [Pterodactyl Egg notes](docs/PTERODACTYL_EGG.md).

## Security

Do not commit passwords, tokens, API keys, private conversations, personal memories, uploaded documents, databases, backups or encryption keys. Ollama is configured for loopback-only access and cloud features are disabled. A hidden Pterodactyl variable is not a secure secret store. See [SECURITY.md](SECURITY.md) for reporting vulnerabilities.

## Contributing

Contributions and suggestions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

## Licence

This project is intended to be released under the MIT Licence. See [LICENSE](LICENSE).
