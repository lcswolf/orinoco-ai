# Orinoco AI

A self-hosted personal AI assistant with local inference, persistent memory, Discord integration and web research.

> **Project status: early implementation / scaffolding.** Orinoco is not yet a working assistant. Features described below are goals, not claims of existing functionality.

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

The initial deployment is intended for Ubuntu 24.04 LTS on a rented VPS, with Pterodactyl Panel 1.13.0 managing Orinoco through a custom Egg and Docker image. The planned stack includes Ollama for local inference, a web application, and optional integrations such as SearXNG and Discord.

The exact implementation and resource requirements will be validated before deployment. No VPS purchase or production deployment is implied by this repository.

## Repository status

The repository includes an initial FastAPI application scaffold, a health endpoint, automated tests, a Pterodactyl-oriented Docker image foundation, and a **preview Pterodactyl 1.x Egg**. It is not yet a usable AI assistant: authentication, chat, database, Ollama integration, Discord and search are still to come. The Docker image has not yet been built or published, and the Egg has not yet been imported into a live Panel.

See [Project Status](docs/PROJECT_STATUS.md), [Architecture](docs/ARCHITECTURE.md), [Development](docs/DEVELOPMENT.md) and [Pterodactyl Egg notes](docs/PTERODACTYL_EGG.md).

## Security

Do not commit passwords, tokens, API keys, private conversations, personal memories, uploaded documents, databases, backups or encryption keys. A hidden Pterodactyl variable is not a secure secret store. See [SECURITY.md](SECURITY.md) for reporting vulnerabilities.

## Contributing

Contributions and suggestions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

## Licence

This project is intended to be released under the MIT Licence. See [LICENSE](LICENSE).
