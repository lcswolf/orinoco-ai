# Orinoco AI

**A self-hosted, privacy-focused AI assistant powered by local models.**

Orinoco is designed to give individuals, communities and hosting teams a friendly assistant they can run and manage themselves. It uses Ollama for local language-model inference and a custom web interface built for Orinoco.

> **Project status: active development / staging preview.** Core application features are implemented, and a container image has been published to GitHub Container Registry. Public anonymous pull access and live Pterodactyl installation are still to be verified. Orinoco is not production-ready.

## What Orinoco is aiming to provide

- **Private multi-user chat** with account-scoped conversation history.
- **Local AI inference** through Ollama; no hosted AI inference API is part of the design.
- **Personal memory controls** so users can review, correct and delete their own saved memories.
- **Private and shared document libraries** with bounded text extraction and keyword retrieval.
- **Optional web research** through an administrator-configured SearXNG service.
- **Welsh and English support**, including per-user reply-language preferences.
- **Administrator controls** for accounts, the shared assistant persona and operational settings.
- **Pterodactyl-oriented operations**, with a custom Egg and a Panel-first day-to-day management goal.
- **Encrypted backups and recovery tooling**, with optional S3-compatible off-site uploads.

Discord text integration and voice features are planned, not currently available. See [Project Status](docs/PROJECT_STATUS.md) for the implementation breakdown.

## Design principles

1. **Privacy by default:** conversations, memories and private documents belong to individual accounts.
2. **Local inference:** prompts are sent to the local Ollama service, not a third-party AI inference API.
3. **Secure boundaries:** retrieved webpages and documents are untrusted reference material, not instructions.
4. **Modular growth:** optional integrations should not burden installations that do not need them.
5. **Hardware awareness:** the long-term design must adapt to the CPU, memory and acceleration actually available to the container.
6. **Honest status:** documentation distinguishes implemented, tested, staging-only and planned features.

## Getting started

Start with the [Documentation Index](docs/README.md).

- New users and operators: [User and Setup Guide](docs/USER_GUIDE.md)
- Pterodactyl operators: [Pterodactyl Egg notes](docs/PTERODACTYL_EGG.md) and [Test VPS Runbook](docs/TEST_VPS_RUNBOOK.md)
- Developers: [Development Guide](docs/DEVELOPMENT.md) and [Contributing](CONTRIBUTING.md)
- Technical overview: [Architecture](docs/ARCHITECTURE.md)
- Current capabilities and release gates: [Project Status](docs/PROJECT_STATUS.md)

**Important:** the setup guide is a preview, not a production deployment recipe. Do not deploy to a live multi-user service until the release gates in Project Status have been completed.

## Container image

The project has published an immutable test image:

- `ghcr.io/lcswolf/orinoco-ai:sha-bcbd697a18dafc7edde55127d28554faad487539`
- OCI index digest: `sha256:98dac555b4efad1da9b7306a09a30df5a8b25a57520fc0227590f7dd7885ff0`

The `stable` tag is also published, but release operators should use the exact immutable tag/digest recorded for the release being tested. Anonymous/public pull access has not yet been independently verified. The image has not yet passed a live Pterodactyl Panel 1.13.0 import and deployment test.

## Repository map

| Path | Purpose |
| --- | --- |
| `orinoco/` | FastAPI application and feature modules |
| `orinoco/static/` | Web interface assets |
| `docker/` | Container image and supervised startup |
| `egg/` | Pterodactyl Egg definition |
| `tests/` | Automated tests |
| `scripts/` | Developer and evaluation utilities |
| `docs/` | User, operator, architecture and development documentation |

## Security and privacy

Do not commit passwords, tokens, API keys, private conversations, personal memories, uploaded documents, databases, backups or encryption keys. Keep Ollama, the database and application data private. A hidden Pterodactyl variable is not a secure secret vault: processes inside the container can read environment variables.

Read [SECURITY.md](SECURITY.md) before exposing an instance to a network or handling other people's data. Report vulnerabilities privately using GitHub's private vulnerability reporting where available.

## Contributing

Suggestions, bug reports and contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) and the [documentation conventions](docs/README.md#documentation-conventions) before submitting changes.

## Licence

Orinoco AI is released under the MIT Licence. See [LICENSE](LICENSE).
