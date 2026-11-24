# Orinoco AI

A self-hosted personal AI assistant with local inference, persistent memory, private documents, web research and planned Discord integration.

> **Project status: early implementation.** The custom interface, local model runtime, authentication, private chat, personal memory, document libraries and explicit SearXNG search workspace are implemented. Orinoco is not yet production-ready.

## Project goals

Orinoco aims to provide a friendly, private assistant that can be hosted on a modest VPS and use locally-run language models.

- Custom Orinoco web interface rather than Open WebUI.
- Local model inference through Ollama, without external AI inference APIs.
- Private administrator and standard-user accounts.
- Per-user chat history and personal memories, with review, correction and deletion controls.
- Private user documents and an administrator-managed shared knowledge library.
- Optional web search through a configured SearXNG instance.
- User-triggered summaries of public webpages, fetched with SSRF protections and summarised by the local model.
- Optional Discord text integration and explicitly activated voice features (planned).

## Design principles

- **Privacy by default:** user conversations, documents and memories remain separated.
- **Local inference:** prompts are processed by a model hosted alongside Orinoco.
- **Safe retrieval:** webpages and documents are untrusted input and must not override system or user instructions.
- **Small-server friendly:** resource usage and model choices should suit modest VPS hardware.
- **Transparent operation:** distinguish verified information from uncertainty and provide source links where applicable.

## Planned deployment

The initial deployment is intended for Ubuntu 24.04 LTS on a rented VPS, with Pterodactyl Panel 1.13.0 managing Orinoco through a custom Egg and Docker image. The container foundation includes a pinned Ollama CPU runtime, a supervisor, first-run model download and separate liveness/readiness checks.

## Repository status

The repository includes a custom responsive interface, secure authentication, administrator user management, authenticated local chat, private conversations and memories, private/shared document libraries, SQLite FTS5 retrieval and an explicit web-search workspace that uses an administrator-configured SearXNG service.

Encrypted local backups, verified S3-compatible off-site uploads, a supervised daily scheduler and configurable local retention are implemented. Remote bucket lifecycle retention and restore-from-remote convenience remain outstanding. Discord, voice and production deployment are not implemented yet. The expanded Docker image is being validated and has not been published to GHCR or deployed.

See [Project Status](docs/PROJECT_STATUS.md), [Architecture](docs/ARCHITECTURE.md), [Development](docs/DEVELOPMENT.md), [Pre-release Audit](docs/PRE_RELEASE_AUDIT.md) and [Pterodactyl Egg notes](docs/PTERODACTYL_EGG.md).

## Security

Do not commit passwords, tokens, API keys, private conversations, personal memories, uploaded documents, databases, backups or encryption keys. Ollama is configured for loopback-only access and cloud features are disabled. A hidden Egg variable is not a secure secret store. See [SECURITY.md](SECURITY.md) for reporting vulnerabilities.

## Contributing

Contributions and suggestions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

## Licence

This project is intended to be released under the MIT Licence. See [LICENSE](LICENSE).
