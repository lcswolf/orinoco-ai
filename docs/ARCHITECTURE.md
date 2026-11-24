# Architecture Proposal

**Status: proposed; subject to change during implementation.**

## Goals

Orinoco should be a private, multi-user assistant that can run on modest VPS hardware, use local model inference and keep each user's private data separate.

## High-level components

- **Web application:** user interface, authentication, chat orchestration and administration.
- **Application database:** accounts, settings, conversations, memory metadata and document records.
- **Ollama:** local model runtime. It should be reachable only on an internal container network.
- **Retrieval layer:** indexes authorised documents and retrieves relevant passages for a user's request.
- **Web research adapter:** optional search and URL retrieval. External webpages are untrusted data.
- **Discord adapter:** optional text integration, with per-channel participation settings.
- **Voice components:** future, opt-in speech recognition and speech output. Listening must start only after an explicit user action.
- **Operations layer:** health checks, logs, backups, restore and controlled updates.

The final choice of framework, database, vector store and process layout remains open until the first implementation design is reviewed.

## Deployment proposal

The initial target is Ubuntu 24.04 LTS on a separate VPS. Pterodactyl will manage the Orinoco server through a custom Egg and Docker image.

The first deployment is intended to use one main Egg, with the application and required processes supervised inside the container. Components may be split into separate managed services later if that proves more reliable.

SearXNG may be hosted separately to reduce memory pressure. It is optional and must be configured explicitly.

## Network boundaries

- Public ingress should be limited to the HTTPS reverse proxy and the minimum ports needed for certificate issuance.
- The web application should receive traffic through the proxy and its assigned service allocation.
- Ollama and the database must not be exposed publicly.
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

Model selection and downloads must be validated against available disk and memory. Model updates must not erase application data.

Retrieved webpages and documents must be treated as untrusted content. They must not be allowed to override system policy, reveal other users' data or trigger privileged actions.

## Backups and updates

Backups should cover the database, configuration, user documents, memory and other persistent application data. They should be encrypted and stored off the VPS, with restore tests performed regularly.

Application, Egg/image and model updates are separate operations. Updates should verify the release, create a backup, apply migrations, run health checks and provide a documented rollback route.

## Open design decisions

- Application framework and database.
- Retrieval/indexing technology.
- Exact process supervision strategy.
- Whether the web interface is fully custom or uses an existing UI component.
- Model download and validation mechanism.
- Backup destination and encryption/key-management approach.
