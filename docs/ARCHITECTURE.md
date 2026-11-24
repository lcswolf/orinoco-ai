# Architecture Proposal

**Status: implementation in progress; deployment details remain subject to testing.**

## Goals

Orinoco should be a private, multi-user assistant that can run on modest VPS hardware, use locally-run language models and keep each user's private data separate.

## High-level components

- **Custom web interface:** lightweight HTML, CSS and JavaScript served by FastAPI. It now includes sign-in, authenticated chat, conversation history, account settings, memory controls and private/shared document-library screens.
- **Web application:** Python/FastAPI. It serves the interface, liveness/readiness endpoints and authenticated account, chat, document and research APIs.
- **Local inference:** Ollama, running in the same Pterodactyl container under Supervisor. Its API binds only to 127.0.0.1:11434; it is not exposed as a public allocation.
- **Model storage:** persistent /home/container/data/models directory. The first-run initialiser downloads the configured curated model when automatic download is enabled.
- **Application database:** SQLite schema v6 stores accounts, per-user response preferences, the administrator-managed core persona, conversations, personal memories and document metadata/extracted text. Access is scoped server-side to the owning user or the authorised shared library.
  Schema upgrades are versioned and additive; an older image refuses a database with a newer schema. Application rollback must therefore restore the pre-update database backup before starting the older image.
- **Retrieval layer:** SQLite FTS5 indexes extracted document text and retrieves bounded keyword excerpts from the current user's private documents and the shared library. This is a lightweight keyword system, not vector/semantic search.
- **Web research adapter:** optional search and URL retrieval. External webpages are untrusted input.
- **Discord adapter:** optional text integration, with per-channel participation settings.
- **Voice components:** future, opt-in speech recognition and speech output. Listening must start only after an explicit user action.
- **Operations layer:** process supervision, health checks, logs, backups, restore and controlled updates.

## Custom interface direction

The interface is being built specifically for Orinoco rather than embedding Open WebUI. The interface uses lightweight static assets served by FastAPI, with no separate JavaScript framework or Node build service. Its visual identity uses an original Womble-inspired woodland helper mascot, woodland greens and warm brass accents, with UK-friendly copy and Europe/London defaults. It includes a responsive workspace layout, Orinoco greeting, service status, authenticated chat, saved conversations with owner-only deletion, account settings, personal memories, document libraries and the research workspace.

The current interface supports authenticated chat, owner-only conversation deletion, per-user response voice/tone/detail preferences, administrator-managed core persona and humour settings, password changes, personal memory controls and document uploads. Pagination and streaming can be added later. Server-side authorisation is required for every account-specific operation.

## Deployment proposal

The initial target is Ubuntu 24.04 LTS on a separate VPS. Pterodactyl Panel 1.13.0 will manage the Orinoco server through a custom Egg and Docker image.

The initial layout uses one Pterodactyl server/container. Supervisor manages Ollama, first-run model initialisation and the web application. Components may be split into separate managed services later if that proves more reliable.

The current image pins Ollama 0.40.18 and configures CPU inference, a single loaded model, one parallel request, a 2048-token default context and a short model keep-alive. These defaults are intended to limit memory use on the proposed 6 GiB VPS and must be measured under real load.

SearXNG may be hosted separately to reduce memory pressure. It is optional and must be configured explicitly.

## Network boundaries

- Public ingress should be limited to the HTTPS reverse proxy and the minimum ports needed for certificate issuance.
- The web application should receive traffic through the proxy and its assigned Pterodactyl allocation.
- Ollama binds to loopback inside the Orinoco container; it must not receive a public allocation.
- SQLite and all application data files remain inside the private container data directory; no database port is exposed.
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

## Document handling

Users can upload private TXT, Markdown, PDF, DOCX, XLSX and PPTX files, with a 10 MiB per-file limit. Administrators can add files to a shared read-only library. Extracted text is stored in SQLite and indexed with FTS5; original files live in a private persistent data directory with generated storage names. Scanned PDFs without embedded text are not OCR-processed.

Relevant excerpts are selected from the signed-in user's own private documents plus shared documents. Retrieved content is untrusted reference material and must never be treated as instructions. Upload parsing is bounded by file size, page/slide/cell limits and extracted-text limits.

## Model and prompt handling

The model is a replaceable local inference backend, not the Orinoco persona itself. Persona and user preferences should be configuration stored by the application.

The initial curated choices are Qwen 2.5 0.5B, 1.5B and 3B, with 1.5B as the default. Model selection and downloads must be validated against available disk and memory. Model updates must not erase application data.

Retrieved webpages and documents must be treated as untrusted content. They must not be allowed to override system policy, reveal other users' data or trigger privileged actions.

## Backups and updates

Encrypted backup tooling creates a SQLite online snapshot, uploaded document tree and file-based session secret, with AES-256-GCM authentication and a verification/restore CLI. Encrypted backups can be uploaded to a private S3-compatible destination over HTTPS; the remote object is downloaded and hashed to verify its bytes. Large Ollama model weights are excluded and can be downloaded again. The encryption key and any environment-supplied secrets must be stored separately. A supervised daily scheduler now creates encrypted local backups, optionally uploads and verifies them off-site, records success/failure status and applies local retention only after a successful backup cycle. Remote bucket lifecycle retention and convenient remote restore remain operational work before deployment. Restore must be run with the app stopped and must be tested regularly.

Application, Egg/image and model updates are separate operations. A manual Pterodactyl update/rollback runbook is documented in `UPDATING.md`; automated migration/update safeguards and a live rollback drill remain outstanding. Updates must verify the release, create and verify a backup, apply migrations, run health checks and preserve the previous image for rollback.

## Remaining operational decisions

- Remote object-storage lifecycle/retention policy and restore-from-remote convenience.
- Application update, database migration and rollback workflow.
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
