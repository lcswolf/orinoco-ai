# Architecture Proposal

**Status: implementation in progress; deployment details remain subject to testing.**

## Goals

Orinoco should be a private, multi-user assistant that can run on modest VPS hardware, use locally-run language models and keep each user's private data separate.

## High-level components

- **Custom web interface:** lightweight HTML, CSS and JavaScript served by FastAPI. The first responsive interface shell is committed; chat, accounts, settings and admin screens will be added as their secure backend features are implemented.
- **Web application:** Python/FastAPI. It serves the interface, liveness/readiness endpoints and future authenticated application APIs.
- **Local inference:** Ollama, running in the same Pterodactyl container under Supervisor. Its API binds only to 127.0.0.1:11434; it is not exposed as a public allocation.
- **Model storage:** persistent /home/container/data/models directory. The first-run initialiser downloads the configured curated model when automatic download is enabled.
- **Application database:** planned for accounts, settings, conversations, memory metadata and document records.
- **Retrieval layer:** planned to index authorised documents and retrieve relevant passages for a user's request.
- **Web research adapter:** optional search and URL retrieval. External webpages are untrusted input.
- **Discord adapter:** optional text integration, with per-channel participation settings.
- **Voice components:** future, opt-in speech recognition and speech output. Listening must start only after an explicit user action.
- **Operations layer:** process supervision, health checks, logs, backups, restore and controlled updates.

## Custom interface direction

The interface is being built specifically for Orinoco rather than embedding Open WebUI. The first page uses lightweight static assets served by FastAPI, with no separate JavaScript framework or Node build service. It includes a responsive workspace layout, Orinoco greeting, service status and clear placeholders for future chat and account features.

The initial chat composer is intentionally not active yet. Authentication, per-user conversation storage and server-side authorisation must be implemented before an unrestricted chat endpoint is exposed. The design should grow in stages: authenticated chat first, then chat history, user preferences, memory/document areas and administrator settings.

## Deployment proposal

The initial target is Ubuntu 24.04 LTS on a separate VPS. Pterodactyl Panel 1.13.0 will manage the Orinoco server through a custom Egg and Docker image.

The initial layout uses one Pterodactyl server/container. Supervisor manages Ollama, first-run model initialisation and the web application. Components may be split into separate managed services later if that proves more reliable.

The current image pins Ollama 0.40.18 and configures CPU inference, a single loaded model, one parallel request, a 2048-token default context and a short model keep-alive. These defaults are intended to limit memory use on the proposed 6 GiB VPS and must be measured under real load.

SearXNG may be hosted separately to reduce memory pressure. It is optional and must be configured explicitly.

## Network boundaries

- Public ingress should be limited to the HTTPS reverse proxy and the minimum ports needed for certificate issuance.
- The web application should receive traffic through the proxy and its assigned Pterodactyl allocation.
- Ollama binds to loopback inside the Orinoco container; it must not receive a public allocation.
- The future database must remain internal.
- Discord and search integrations require outbound connectivity.
- Private remote access may be provided through Tailscale; public exposure through a private-network tunnel is not required.

Exact ports, firewall rules and Pterodactyl/Wings compatibility must be verified during deployment.

## Identity and data isolation

Every private record must be associated with an authenticated user or an explicitly shared scope.

- Users can access their own conversations, memories and private documents.
- Standard users may read authorised shared-library content but cannot administer it.
- Administrators manage accounts, shared content and core assistant settings.
- Account linking for Discord must use a verified account association, not a display name.
- Memory review, correction and deletion must be available to the owning user.

Authorisation must be enforced server-side for every data access; hiding controls in the interface is not sufficient.

## Model and prompt handling

The model is a replaceable local inference backend, not the Orinoco persona itself. Persona and user preferences should be configuration stored by the application.

The initial curated choices are Qwen 2.5 0.5B, 1.5B and 3B, with 1.5B as the default. Model selection and downloads must be validated against available disk and memory. Model updates must not erase application data.

Retrieved webpages and documents must be treated as untrusted content. They must not be allowed to override system policy, reveal other users' data or trigger privileged actions.

## Backups and updates

Backups should cover the database, configuration, user documents, memory and other persistent application data. They should be encrypted and stored off the VPS, with restore tests performed regularly.

Application, Egg/image and model updates are separate operations. Updates should verify the release, create a backup, apply migrations, run health checks and provide a documented rollback route.

## Open design decisions

- Database and persistence framework.
- Retrieval/indexing technology.
- Model update and migration workflow.
- Backup destination and encryption/key-management approach.
