# Architecture and Deployment Design

**Status: implementation in progress; deployment details remain subject to testing.**

## Goals

Orinoco should be a private, multi-user assistant that can run on modest VPS hardware, use locally-run language models and keep each user's private data separate.

## High-level components

- **Custom web interface:** lightweight HTML, CSS and JavaScript served by FastAPI. It now includes sign-in, authenticated chat, conversation history, account settings, memory controls and private/shared document-library screens.
- **Web application:** Python/FastAPI. It serves the interface, liveness/readiness endpoints and authenticated account, chat, document and research APIs.
- **Local inference:** Ollama, running in the same Pterodactyl container under Supervisor. Its API binds only to 127.0.0.1:11434; it is not exposed as a public allocation.
- **Model storage:** persistent /home/container/data/models directory. The first-run initialiser downloads the configured curated model when automatic download is enabled.
- **Application database:** SQLite schema v9 stores accounts, per-user response preferences (including automatic/English/Welsh reply language), the administrator-managed core persona, conversations, personal memories and document metadata/extracted text. Access is scoped server-side to the owning user or the authorised shared library.
  Schema upgrades are versioned and additive; an older image refuses a database with a newer schema. Application rollback must therefore restore the pre-update database backup before starting the older image.
- **Retrieval layer:** SQLite FTS5 indexes extracted document text and retrieves bounded keyword excerpts from the current user's private documents and the shared library. This is a lightweight keyword system, not vector/semantic search.
- **Web research adapter:** optional search and URL retrieval. External webpages are untrusted input.
- **Discord adapter:** optional text integration, with per-channel participation settings.
- **Voice components:** future, opt-in speech recognition and speech output. Listening must start only after an explicit user action.
- **Operations layer:** process supervision, health checks, logs, backups, restore and controlled updates.

## Custom interface direction

The interface is being built specifically for Orinoco rather than embedding Open WebUI. The interface uses lightweight static assets served by FastAPI, with no separate JavaScript framework or Node build service. Its visual identity uses an original Womble-inspired woodland helper mascot, woodland greens and warm brass accents, with UK-friendly copy and Europe/London defaults. It includes a responsive workspace layout, Orinoco greeting, service status, authenticated chat, saved conversations with owner-only deletion, account settings, personal memories, document libraries and the research workspace.

The current interface supports authenticated chat, owner-only conversation deletion, per-user response voice/tone/detail preferences, administrator-managed core persona and humour settings, password changes, personal memory controls and document uploads. The approved expansion into a persistent, versioned administrator-managed identity profile (name, creator, purpose, background, personality and behaviour) is specified in [Identity & Behaviour Configuration](IDENTITY_CONFIGURATION.md); that broader feature is not yet implemented. Pagination and streaming can be added later. Server-side authorisation is required for every account-specific operation.

## Deployment proposal

The initial target is Ubuntu 24.04 LTS on a separate VPS. Pterodactyl Panel 1.13.0 (stable 1.x release line) will manage the Orinoco server through a custom Egg and Docker image.

The initial layout uses one Pterodactyl server/container. Supervisor manages Ollama, first-run model initialisation and the web application. Components may be split into separate managed services later if that proves more reliable.

The current image pins Ollama 0.40.18 and configures CPU inference, a single loaded model, one parallel request, a 2048-token default context and a short model keep-alive. These defaults are intended to limit memory use on the proposed 6 GiB VPS and must be measured under real load. The resource-detection implementation adds startup discovery of effective CPU affinity, cpuset and cgroup v1/v2 CPU quota, plus cgroup memory limit/current usage. `AI_THREADS=0` selects the detected CPU count for Ollama's per-request `num_thread`; a positive administrator-only value may reduce but not exceed that allocation. Memory is reported in diagnostics, but the selected model and context are never silently changed.

SearXNG may be hosted separately to reduce memory pressure. It is optional and must be configured explicitly.

## Network boundaries

The current host-proxy design is documented in [Network Deployment](NETWORK_DEPLOYMENT.md). It uses Caddy for public TLS, Nginx on loopback for per-client rate/body/connection limits, and a separate Tailscale Serve endpoint for private access. The intended browser paths are the HTTPS subdomain, HTTPS public IP on port 8443, and the HTTPS tailnet DNS name on port 8444.

- Public ingress is limited to TCP 80/443 for ACME and the subdomain, plus TCP 8443 for HTTPS by IP. SSH and Panel/Wings management ports are restricted to approved administration networks.
- Nginx listens on 127.0.0.1:8081 and proxies to the Pterodactyl allocation. The allocation must be blocked from direct public access using the actual Docker/Wings firewall path.
- Tailscale Serve proxies to the same local Nginx listener and remains tailnet-only; Funnel is not used.
- The Orinoco container explicitly disables Uvicorn forwarded-header processing until the real trusted proxy peer address is measured and allow-listed. Nginx enforces public per-client limits at the edge.
- Ollama binds to loopback inside the Orinoco container and receives no public allocation.
- SQLite and all application data files remain inside the private container data directory; no database port is exposed.
- Discord and search integrations require outbound connectivity.

This is a configuration plan, not a deployed firewall. Exact addresses, ports, Docker rules and Pterodactyl/Wings compatibility must be verified on the live Leaseweb node.

## Identity and data isolation

Every private record must be associated with an authenticated user or an explicitly shared scope.

- Users can access their own conversations, memories and private documents.
- Standard users may read authorised shared-library content but cannot administer it.
- Administrators manage accounts, shared content and core assistant settings.
- Account linking for Discord must use a verified account association, not a display name.
- Memory review, correction and deletion must be available to the owning user.

Authorisation must be enforced server-side for every data access; hiding controls in the interface is not sufficient.

## Document handling

Users can upload private TXT, Markdown, PDF, DOCX, XLSX and PPTX files, with a 10 MiB per-file limit. Administrators can add files to a shared read-only library. Extracted text is stored in SQLite and indexed with FTS5; original files live in a private persistent data directory with generated storage names. Scanned PDFs without embedded text are not OCR-processed.

Relevant excerpts are selected from the signed-in user's own private documents plus shared documents. Retrieved content is untrusted reference material and must never be treated as instructions. Upload parsing is bounded by file size, page/slide/cell limits and extracted-text limits.

## Model and prompt handling

The model is a replaceable local inference backend, not the Orinoco persona itself. Persona and user preferences should be configuration stored by the application.

The initial curated choices are Qwen 2.5 0.5B, 1.5B and 3B, with 1.5B as the default. Reply language preference is account-scoped; automatic mode follows the latest user message, while English and Welsh settings establish the preferred response language. The selected model's Welsh/English quality must be measured locally before release. Model selection and downloads must be validated against available disk and memory. Model updates must not erase application data.

Retrieved webpages and documents must be treated as untrusted content. They must not be allowed to override system policy, reveal other users' data or trigger privileged actions.

## Backups and updates

Encrypted backup tooling creates a SQLite online snapshot, uploaded document tree and file-based session secret, with AES-256-GCM authentication and a verification/restore CLI. Encrypted backups can be uploaded to a private S3-compatible destination over HTTPS; the remote object is downloaded and hashed to verify its bytes. Large Ollama model weights are excluded and can be downloaded again. The encryption key and any environment-supplied secrets must be stored separately. Orinoco also provides an optional supervised daily encrypted-backup scheduler, disabled by default so Pterodactyl scheduled backups can serve as the primary routine backup system. When explicitly enabled, it can upload and verify backups off-site, record success/failure status and apply local retention only after a successful backup cycle. Manual encrypted backup/restore tooling remains available regardless of the scheduler setting. Remote bucket lifecycle retention and convenient remote restore remain operational work before deployment. Restore must be run with the app stopped and must be tested regularly.

Application, Egg/image and model updates are separate operations. A manual Pterodactyl update/rollback runbook is documented in `UPDATING.md`. The `orinoco.updates` CLI creates and verifies a pre-update backup, optionally uploads it to the configured S3-compatible bucket, and requires a verified backup before applying additive SQLite migrations. Automated image switching and a live upgrade/rollback drill remain outstanding. Updates must verify the release, create and verify a backup, apply migrations, run health checks and preserve the previous image for rollback.

## Configuration and lifecycle requirements

The product is intended to grow through administrator-managed configuration rather than separate editions. Optional modules should be independently enableable/disableable from the Orinoco administrator interface and/or Pterodactyl variables, according to the responsibility of each setting. Disabling a module must stop its background work and routes as well as hide its user interface; stored data and settings should be preserved unless an administrator explicitly deletes them. Configuration changes should be validated, show dependency information and take effect through a controlled restart.

The administrator interface and advanced settings must remain separate from the ordinary user experience. Standard users should see only the features enabled for them and their own account data. Backend authorization is mandatory; hiding an administrator control in the browser is not a security boundary.

The assistant identity is intended to be model-independent. A persistent administrator-managed profile is planned for the assistant's name, purpose, creator/organisation, background, core uses and communication style. It must remain separate from per-user preferences and from application-owned privacy, safety and permission guardrails. See the identity configuration design when it is merged into the main branch.

Hardware-aware startup configuration is also a core requirement: detect the resources actually available to the container (including CPU and memory limits), then select safe inference thread and request-concurrency defaults. Preserve administrator-selected models and module preferences; warn rather than silently replace a model that no longer fits. Performance history and benchmarking are planned to support comparisons between VPS sizes. These behaviours are design requirements, not claims of current implementation.
## Remaining operational decisions

- Remote object-storage lifecycle/retention policy and restore-from-remote convenience.
- Automated image switching and a live update/rollback drill; the backup-gated migration CLI and operator runbook are implemented.
- Final off-site object-storage provider and operational key-management procedure.
- Reverse-proxy request/rate limits and the exact public/private access arrangement.

## Source-code map

The repository is organised by responsibility so that features can grow without putting every concern into one module:

| Path | Responsibility |
| --- | --- |
| `orinoco/main.py` | FastAPI application assembly, static interface and health/readiness endpoints |
| `orinoco/auth/` | Password hashing, signed sessions with per-account revocation versions, and authentication routes |
| `orinoco/admin/` | Administrator API and first-admin bootstrap command (`python -m orinoco.admin`) |
| `orinoco/chat/` | Conversation API, prompt construction and local model orchestration |
| `orinoco/memories/` | Authenticated personal-memory API |
| `orinoco/memory/store.py` | Compatibility helpers backed by the shared database layer |
| `orinoco/documents/` | Upload validation, bounded Office archive checks, text extraction, private/shared routes and file storage |
| `orinoco/llm/` | Local Ollama HTTP client |
| `orinoco/research/` | SearXNG search client and SSRF-resistant public webpage fetching |
| `orinoco/backups.py` | Encrypted backup, restore and S3-compatible upload CLI |
| `orinoco/updates.py` | Verified pre-update backup and backup-gated SQLite migration CLI |
| `orinoco/db.py` | SQLite schema and account-scoped persistence operations |
| `orinoco/static/` | Browser interface (HTML, CSS, JavaScript and original mascot SVG) |
| `docker/` | Image definition, Pterodactyl entrypoint and supervised service startup |
| `egg/` | Pterodactyl Egg definition and installation script |
| `tests/` | Automated behaviour, isolation and runtime checks |

Keep module boundaries intact: API routes should authenticate and validate requests, while database functions enforce ownership in their queries as a second line of defence. Document extraction should not decide who may access a file; route and persistence layers enforce that policy.

## Maintaining the code

Python modules use module docstrings and functions/classes use docstrings where their purpose, ownership rules, side effects or failure behaviour are not obvious from their names. Frontend and shell files use concise section comments for operationally important flows. Comments should explain why a constraint exists rather than repeat the statement below it. See [Development](DEVELOPMENT.md) for the full documentation conventions.
