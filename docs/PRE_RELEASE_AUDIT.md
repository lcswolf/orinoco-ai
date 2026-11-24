# Orinoco pre-release audit

**Status: in progress — do not deploy to a public VPS yet.**

Latest completed CI run: 109 tests passed, with one Starlette/httpx TestClient deprecation warning. The Node 20 GitHub Actions warning has been removed by upgrading the workflow actions. The current container build and runtime smoke test are still pending.

This is the working checklist for a repository-wide review before the first production deployment. The audit checks implementation, tests, documentation, runtime packaging and the Pterodactyl Egg together. A passing unit-test suite is useful evidence, but it is not a substitute for a live deployment and recovery test.

## Audit scope

- Authentication, authorisation, session cookies, CSRF and account bootstrap.
- Per-user isolation for conversations, memories and private documents.
- Database schema, migrations, transactions, indexes and file/database consistency.
- Chat prompts, model errors, resource limits and untrusted retrieved content.
- Web search and webpage fetching, including SSRF and redirect handling.
- Document upload, extraction, storage paths, download and deletion.
- Encrypted backup creation, remote transfer, verification and restore.
- Docker image, non-root runtime, process supervision, model download and persistent paths.
- Pterodactyl Panel 1.x Egg schema, startup command, variables, allocations and resource assumptions.
- Frontend behaviour, accessibility, responsive layout and safe rendering of untrusted text.
- CI coverage, dependency health, comments/docstrings and user-facing documentation.

## Confirmed findings and corrections

### First-admin bootstrap command — corrected

The repository contained both `orinoco/admin.py` and the `orinoco/admin/` package. Python resolves the package for `python -m orinoco.admin`, so the documented first-admin command did not execute the standalone module. The command is now implemented by `orinoco/admin/__main__.py` and `orinoco/admin/cli.py`. The CLI also resolves and passes the configured database path explicitly, so the documented `ORINOCO_DATABASE_PATH` override is respected.

A regression test has been added for the bootstrap command and its selected database path.

### Duplicate memory route implementation — corrected

There were two implementations of the same `/api/memories` routes. The application registered the plural `orinoco.memories.routes` implementation; the unused singular `orinoco.memory.routes` implementation has been removed. The singular package remains only for shared compatibility helpers.

### Database docstrings — corrected

Several database function docstrings had been placed inside conditionals or transaction blocks, where Python did not recognise them as function docstrings. They have been moved to the correct function positions to improve maintainability and generated help/documentation.

### Remote backup verification — strengthened

The first S3-compatible upload implementation checked object size and client-supplied SHA-256 metadata. Metadata alone does not prove the bytes stored by the remote service match the source. Upload verification now downloads the stored object and hashes the returned bytes as well. Symbolic-link backup sources are rejected before resolving the path. Regression tests cover altered remote bytes and symbolic-link inputs.

### Document deletion and storage path handling — strengthened

Private and shared document deletion now removes the original file before deleting its database record. If file cleanup fails, the record remains visible and the user/administrator receives an error so cleanup can be retried; failures during upload rollback are logged. Stored paths now reject traversal and final-component symbolic links. Upload, deletion, backup and restore operations share a cross-process file lock so a backup cannot snapshot database metadata and document files from opposite sides of an in-progress file operation. The lock uses POSIX flock on the Linux VPS and an msvcrt byte-range fallback for Windows development.

### Office document decompression limits — strengthened

DOCX, XLSX and PPTX uploads are ZIP archives. A small compressed file can expand into a much larger payload, so the extraction path now checks archive entry counts, encrypted entries and both declared and actual uncompressed size before parsing. A regression test uses a highly-compressible oversized archive to verify the limit.

### Restore rollback — strengthened

The restore path now creates its pre-restore database snapshot through SQLite's online backup API, preserving committed WAL data. It also preserves the existing file-based session secret as a persistent pre-restore recovery copy and restores it if a later restore step fails. Failure-injection and successful-restore regression tests cover these paths.

### Chat reference-context formatting — corrected

Several prompt-context separators had been double-escaped, causing the model to receive literal backslash-n text instead of readable line breaks. They now use actual newline characters, with a regression assertion covering document context formatting.

### Automatic memory sensitive-data filtering — strengthened

The model-generated memory filter now uses word-boundary matching and covers additional common medical, financial, religious, political, sexual-orientation and criminal-history terms. This is a conservative keyword filter, not a guarantee that every sensitive fact can be recognised; the prompt, user review controls and privacy review remain important.

### Browser security headers — added

The application now sends a restrictive Content Security Policy, clickjacking protection, MIME sniffing protection, a conservative referrer policy, same-origin resource/opener policies and a Permissions Policy disabling unused camera/microphone/geolocation access. The current frontend uses DOM node creation and textContent for dynamic content rather than HTML string injection. Regression tests check the headers on application, API and static responses.

### SQLite schema version safety — strengthened

The database initializer now completes the known additive v1–v3 table/index upgrades to schema v4, and refuses to modify a database with a newer schema version instead of silently resetting its version number. Regression tests cover an early users-only database and a future-version database. Non-additive schema changes will still require an explicit migration before the schema version is increased.

### Local inference boundary — hardened

The production Ollama client and readiness check now use the fixed loopback endpoint. Environment variables and explicit production client URLs cannot redirect prompts to an external inference service; HTTP proxy environment variables are also ignored for Ollama traffic. Only tests that inject a mock transport may use a non-loopback URL. This enforces the agreed local-inference-only architecture.

### Timezone and inactive Egg options — corrected

The runtime now installs the operating-system timezone database so the configured Europe/London timezone is available to Python and scheduled operations. The Discord and voice Egg toggles are now locked off until those integrations actually exist, preventing a server owner from enabling non-functional features.

### Runtime and CI version pins — checked

The Docker image's Ollama pin, `0.40.18`, matches the latest non-prerelease release published on 24 November 2026 ([official Ollama release](https://github.com/ollama/ollama/releases/tag/v0.40.18)). The GitHub Actions workflows have been moved from the older checkout/setup-python major versions to the current Node 24-compatible releases ([checkout v7.0.1](https://github.com/actions/checkout/releases/tag/v7.0.1), [setup-python v7.1.0](https://github.com/actions/setup-python/releases/tag/v7.1.0), [setup-buildx v4.4.1](https://github.com/docker/setup-buildx-action/releases/tag/v4.4.1), [build-push v7.4.0](https://github.com/docker/build-push-action/releases/tag/v7.4.0)). CI must be re-run after this update. One Starlette/httpx TestClient deprecation warning remains under review; it does not currently fail tests.

### Documentation accuracy — corrected

The README and development guide now distinguish implemented encrypted backup operations from the outstanding scheduler/retention work. The Egg's web-search descriptions now reflect the implemented SearXNG integration rather than describing it as future work.

## Remaining review work

- [ ] Add the agreed editable personality controls: administrator-managed core persona and per-user voice, tone and answer-detail preferences. The current default prompt now reflects the bright voice and 65% humour choice, but the settings UI/persistence is not yet implemented.

- [ ] Finish authentication/session review, including rate-limit behaviour, cookie/proxy assumptions, secret rotation and revocation.
- [x] Add regression coverage for known additive schema upgrades and refusal to downgrade a newer database.
- [ ] Review all database functions and schema evolution for safe upgrades from an existing installation.
- [x] Add bounded Office ZIP expansion checks and regression coverage.
- [x] Preserve retryable document records when file deletion fails and reject unsafe stored paths.
- [ ] Finish review of private/shared document ownership, file permissions and parser edge cases. Configure an approximately 11 MiB reverse-proxy request-body limit for document upload routes so oversized multipart bodies are rejected before application parsing.
- [ ] Review the complete chat flow, memory extraction filters, prompt boundaries, queue handling and failure recovery.
- [ ] Complete SSRF and redirect tests for public webpage fetching; review SearXNG endpoint configuration and returned links.
- [x] Strengthen restore rollback for the database, WAL state and file-based session secret.
- [ ] Finish review of encrypted archive edge cases, key handling and remote transfer failure behaviour.
- [ ] Implement and test automatic daily backups, retention and clear failure reporting.
- [ ] Validate the Egg against the target Panel 1.13.0 format and confirm every environment variable matches the runtime.
- [ ] Finalise the Leaseweb VPS deployment plan: Caddy HTTPS, Tailscale Serve for private access (no Funnel), firewall exposure limited to required ports, and reverse-proxy request/rate limits.
- [ ] Validate container startup ordering, process failure handling, writable persistent paths and model-download behaviour.
- [x] Add restrictive browser security headers and verify they apply to application/API/static responses.
- [ ] Finish frontend accessibility, keyboard navigation, mobile layout and API error-state review.
- [ ] Integrate the agreed original Womble-inspired Orinoco mascot and UK-oriented interface treatment; the current UI has a simple logo mark but no mascot artwork yet.
- [ ] Review CI workflow permissions, dependency versions, build reproducibility and vulnerability scanning.
- [ ] Run the complete test suite after all audit corrections; build and smoke-test the final image.
- [ ] Perform a live Pterodactyl test with a disposable server, then test backup restore before considering production readiness.

## Release gate

Do not publish the `stable` image or deploy the Egg until all critical findings are fixed, the full automated suite and container smoke test pass on the same commit, and a live Pterodactyl installation and restore test have been completed. Discord and voice remain optional later milestones; they must not delay or weaken the core security and recovery release gate.
