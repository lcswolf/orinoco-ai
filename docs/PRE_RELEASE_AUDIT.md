# Orinoco pre-release audit

**Status: in progress — do not deploy to a public VPS yet.**

Latest completed Python CI run: 170 tests passed, with one non-failing Starlette/httpx TestClient deprecation warning. The dependency audit reports no known vulnerabilities. The latest container build including conversation deletion, schema v6 and persona settings passed its expanded smoke test. A final CLI error-handling adjustment is being rebuilt.

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

## Authentication review — in progress

### Username lockout denial-of-service — corrected

The first login throttle keyed failed attempts globally by username. That meant a remote client could intentionally lock a known account for the full rolling window by submitting repeated incorrect passwords. The username bucket is now scoped to the username and observed client-address pair, while a separate per-address bucket continues to limit attempts across different usernames. A regression test verifies that a second client is not locked out by the first client's failures. Both trackers remain process-local, so a production reverse proxy must enforce its own shared rate limits, especially where multiple application workers or replicas are used.

Session cookies remain signed, HTTP-only, SameSite=Lax and Secure by default. Password changes and account status changes increment the account session version and revoke older cookies. The file-based signing secret is persistent and owner-only; changing the configured signing secret invalidates existing sessions. Trusted-proxy configuration and a documented operational rotation rehearsal remain deployment checks.

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

Private and shared document deletion now removes the original file before deleting its database record. If file cleanup fails, the record remains visible and the user/administrator receives an error so cleanup can be retried; failures during upload rollback are logged. Stored paths reject traversal, final-component symbolic links and a symbolic-link document root. Upload, deletion, backup and restore operations share a cross-process file lock so a backup cannot snapshot database metadata and document files from opposite sides of an in-progress file operation. The lock uses POSIX flock on the Linux VPS and an msvcrt byte-range fallback for Windows development.

### Office document decompression limits — strengthened

DOCX, XLSX and PPTX uploads are ZIP archives. A small compressed file can expand into a much larger payload, so the extraction path now checks archive entry counts, encrypted entries and both declared and actual uncompressed size before parsing. A regression test uses a highly-compressible oversized archive to verify the limit.

### Login throttling — strengthened

The existing five-attempt per-username rolling window is now paired with a 30-attempt per observed client-address window. Both trackers have hard memory bounds. The application ignores untrusted forwarded-IP headers; reverse-proxy limits are still required for public deployment.

### Persistent session-secret storage — hardened

The persistent session-signing file now rejects symbolic links and is restricted to owner-only permissions when read. Regression tests cover both symlink rejection and repairing permissive file mode bits.

### Restore rollback — strengthened

The restore path now creates its pre-restore database snapshot through SQLite's online backup API, preserving committed WAL data. It also preserves the existing file-based session secret as a persistent pre-restore recovery copy and restores it if a later restore step fails. Failure-injection and successful-restore regression tests cover these paths.

### Chat reference-context formatting — corrected

Several prompt-context separators had been double-escaped, causing the model to receive literal backslash-n text instead of readable line breaks. They now use actual newline characters, with a regression assertion covering document context formatting.

### Automatic memory sensitive-data filtering — strengthened

The model-generated memory filter now uses word-boundary matching and covers additional common medical, financial, religious, political, sexual-orientation/gender-identity and criminal-history terms. It also rejects common prompt-injection candidates that attempt to override system/developer instructions, reveal hidden prompts or bypass safeguards. Regression tests cover these cases. This remains a conservative keyword filter, not a guarantee that every sensitive fact or paraphrase can be recognised; the prompt, user review controls and privacy review remain important.

### Static injection-pattern review — checked

The current source scan found no use of `eval`, `shell=True`, `pickle.loads` or frontend `innerHTML`. The Pterodactyl entrypoint tokenises its startup command with `shlex.split` and replaces the process with `execvp`; it does not evaluate the command through a shell. Continue to review new code against the same rules.

### Account-wide session revocation — implemented

The users table now has a versioned session counter. New sign-ins store that version in the signed cookie; password changes and account suspension/reactivation increment it. All authenticated route groups validate the version, so old cookies cannot become valid again after an account is reactivated. The database performs an additive v4-to-v5 migration, with regression tests for migration, password-change revocation and suspend/reactivate revocation. Existing browser cookies created before this change will require one fresh sign-in after upgrade.

### Login throttle memory use — hardened

The failed-login tracker now applies rolling windows per username and per observed client address, has fixed memory bounds for both maps, and reports the remaining Retry-After window. It remains process-local and deliberately ignores untrusted forwarded-IP headers, so reverse-proxy rate limits and trusted-proxy configuration are still required before public exposure.

### Browser security headers — added

The application now sends a restrictive Content Security Policy, clickjacking protection, MIME sniffing protection, a conservative referrer policy, same-origin resource/opener policies and a Permissions Policy disabling unused camera/microphone/geolocation access. The current frontend uses DOM node creation and textContent for dynamic content rather than HTML string injection. Regression tests check the headers on application, API and static responses.

### SQLite schema version safety — strengthened

The database initializer now completes the known additive v1–v5 table/index and session-version upgrades plus v6 per-user response-preference and administrator-persona tables. It refuses to modify a database with a newer schema version instead of silently resetting its version number. Regression tests cover a v5-to-v6 upgrade without losing accounts, defaults and a future-version database. Non-additive schema changes will still require an explicit migration before the schema version is increased.

### Local inference boundary — hardened

The production Ollama client and readiness check now use the fixed loopback endpoint. Environment variables and explicit production client URLs cannot redirect prompts to an external inference service; HTTP proxy environment variables are also ignored for Ollama traffic. Only tests that inject a mock transport may use a non-loopback URL. This enforces the agreed local-inference-only architecture.

### Timezone and inactive Egg options — corrected

The runtime now installs the operating-system timezone database so the configured Europe/London timezone is available to Python and scheduled operations. The Discord and voice Egg toggles are now locked off until those integrations actually exist, preventing a server owner from enabling non-functional features.

### Runtime and CI version pins — checked

The Docker image's Ollama pin, `0.40.18`, matches the latest non-prerelease release published on 24 November 2026 ([official Ollama release](https://github.com/ollama/ollama/releases/tag/v0.40.18)). The GitHub Actions workflows use Node 24-compatible releases ([checkout v7.0.1](https://github.com/actions/checkout/releases/tag/v7.0.1), [setup-python v7.1.0](https://github.com/actions/setup-python/releases/tag/v7.1.0), [setup-buildx v4.4.1](https://github.com/docker/setup-buildx-action/releases/tag/v4.4.1), [build-push v7.4.0](https://github.com/docker/build-push-action/releases/tag/v7.4.0)). The latest completed Python suite passes 170 tests. One Starlette/httpx TestClient deprecation warning remains under review; it does not currently fail tests. The final release gate will repeat the dependency audit, full suite and container smoke test on the same commit.

### SQLite file permissions and symlink handling — hardened

The database layer now opens/creates the SQLite file with owner-only permissions and rejects symbolic-link database paths before connecting. Regression tests cover both permission mode and link rejection.

### Conversation deletion — implemented

Users can delete their own conversation and all associated messages through a CSRF-protected API. Ownership is enforced in the database DELETE query, and foreign-key cascade removes messages. The interface requires confirmation and explains that existing encrypted backups may retain prior copies until retention expires.

### External research link handling — hardened

The audit found that search-result URLs were assigned directly to browser link elements. The frontend now accepts only absolute, credential-free HTTP(S) URLs before creating links, and applies `noopener noreferrer`. The SearXNG adapter also rejects malformed URLs, local hostnames, private/non-global literal IP addresses and reserved test domains. Untrusted titles and snippets continue to be rendered as text nodes, not HTML.

### Original mascot and woodland interface — integrated

The welcome screen now uses an original Womble-inspired woodland helper SVG, with meaningful alternative text, responsive sizing and no external image/script dependencies. The UI accents have been shifted toward woodland greens and warm brass; the footer identifies the UK-time default. Branding tests check the asset and accessibility hooks.

### Dependency vulnerability audit — corrected

The new pip-audit CI step found seven advisories affecting the resolved `cryptography 46.0.7` package, which the old version range still allowed. The minimum was raised to the patched `50.0.2` release line. A subsequent CI dependency audit reported no known vulnerabilities. Weekly Dependabot updates now monitor Python packages and GitHub Actions.

### Daily encrypted backup scheduling — implemented

A dedicated Supervisor-managed process runs one backup per local calendar day (03:00 by default in the configured timezone). It creates an encrypted local backup, optionally uploads and byte-verifies it to the configured S3-compatible bucket, and prunes expired local backups only after the complete backup cycle succeeds. The default local retention is 14 days and is configurable from 1 to 365. Failures are written to the Pterodactyl console and a private status JSON file. Remote bucket lifecycle retention and restore-from-remote convenience remain outstanding.

### Backup-gated update migrations — implemented

The `orinoco.updates` one-shot CLI creates and verifies a fresh encrypted pre-update backup, uploads it when S3 is configured, and requires a verified backup before applying the additive SQLite migrations to an existing database. The operator runbook explains how to run these commands as temporary Pterodactyl startup commands while the application is stopped. Automated image switching and a live upgrade/rollback drill remain outstanding.

### Chat recovery after memory-store failure — hardened

A failure during automatic memory extraction or persistence is now logged but does not discard an otherwise successful assistant response. A regression test verifies that the conversation is still saved and returned.

### Documentation accuracy — corrected

The README, architecture, Egg and development guide now distinguish implemented daily local scheduling/retention from the outstanding remote bucket lifecycle and remote-restore convenience. The Egg's web-search descriptions reflect the implemented SearXNG integration.

### Request and storage resource limits — application controls implemented

The application now rejects oversized declared request bodies (12 MiB default)
before FastAPI parses them. Chat submissions default to 10 per user per rolling
minute, configurable in the Egg. Private document libraries default to 20 files /
50 MiB per account; the administrator-managed shared library defaults to
50 files / 200 MiB. All resource settings are configurable in the Egg. Upload quota
checks run under the document storage lock, and regression coverage verifies
that one user's quota does not affect another account. The reverse proxy must
still enforce request-body limits for chunked requests and apply an
approximately 11 MiB upload-route limit. The current quota lock is process-local;
a multi-worker deployment needs atomic database quota reservations.

### Chat generation queue — bounded

The chat API now reserves one of a bounded number of in-flight slots before loading account context. The default is one model-generation slot plus eight additional admitted requests; excess requests receive HTTP 503 and `Retry-After: 5`. The additional capacity is configurable from 0–32 in the Egg. A regression test verifies overload rejection and slot release. This limiter is process-local; a multi-worker deployment needs shared queue coordination.

### Reverse-proxy design — documented, not yet deployed

The network plan now documents Caddy public TLS, Nginx loopback-only request/body/rate/connection limits, the public HTTPS subdomain, short-lived IP certificate access on port 8443, and tailnet-only Tailscale Serve on port 8444 without Funnel. Uvicorn is explicitly started with forwarded-header processing disabled until the real proxy peer address can be measured and allow-listed. The live Leaseweb/Pterodactyl host, Docker published-port firewall path, certificate issuance/renewal, actual client IP handling and all three access paths still require verification. See `docs/NETWORK_DEPLOYMENT.md`.

## Remaining review work

- [x] Add administrator-managed core persona and humour controls plus private per-user response voice, tone and answer-detail preferences, including persistence, API authorisation and prompt integration.

- [x] Add bounded per-client-address login throttling alongside per-username limits.
- [x] Add owner-only SQLite file permissions and symbolic-link rejection.
- [ ] Finish authentication/session review, including trusted-proxy configuration and session-secret rotation. Application-level declared-body limits and configurable per-user/shared document quotas are implemented; reverse-proxy limits (including chunked requests), multi-worker quota reservations and chat retention remain outstanding.
- [x] Add regression coverage for known additive schema upgrades and refusal to downgrade a newer database.
- [x] Review SQLite file creation permissions and reject symbolic-link database paths.
- [ ] Continue reviewing database functions and schema evolution for safe upgrades from an existing installation.
- [x] Add bounded Office ZIP expansion checks and regression coverage.
- [x] Preserve retryable document records when file deletion fails and reject unsafe stored paths.
- [ ] Finish review of private/shared document ownership, parser edge cases and cleanup paths. Configure an approximately 11 MiB reverse-proxy request-body limit for document upload routes (and global limits for other routes) so oversized and chunked multipart bodies are rejected before application parsing.
- [ ] Review the complete chat flow, memory extraction filters, prompt boundaries, queue handling and failure recovery.
- [x] Complete SSRF and redirect tests for public webpage fetching; review SearXNG endpoint configuration and returned links.
- [x] Strengthen restore rollback for the database, WAL state and file-based session secret.
- [ ] Finish review of encrypted archive edge cases, key handling and remote transfer failure behaviour.
- [x] Implement and test automatic daily encrypted backups, local retention and failure reporting.
- [ ] Configure remote bucket lifecycle retention and convenient restore-from-remote.
- [x] Add backup-verified pre-update and explicit database migration commands plus a Pterodactyl operator runbook.
- [ ] Validate the Egg against the target Panel 1.13.0 format and confirm every environment variable matches the runtime.
- [ ] Apply and live-test the Caddy/Nginx/Tailscale design in [Network Deployment](NETWORK_DEPLOYMENT.md): public HTTPS subdomain, HTTPS IP:8443, private Tailscale Serve :8444 (no Funnel), Docker/Wings firewall restrictions, edge body/rate/connection limits and certificate renewal.
- [ ] Validate container startup ordering, process failure handling, writable persistent paths and model-download behaviour.
- [x] Add restrictive browser security headers and verify they apply to application/API/static responses.
- [x] Validate external links and render untrusted search/document/chat text without HTML parsing.
- [ ] Finish keyboard navigation, mobile layout and API error-state review.
- [x] Integrate the original Womble-inspired Orinoco mascot, accessible SVG artwork and UK woodland visual treatment.
- [x] Add weekly Dependabot monitoring for Python and GitHub Actions dependencies.
- [x] Add pip-audit to CI and resolve the reported cryptography advisories; the follow-up audit is clean.
- [ ] Continue reviewing dependency updates and build reproducibility.
- [x] Confirm 179 passing tests, a clean pip-audit scan and a scheduler-enabled container build/smoke test (latest Python test run #667; container smoke run #324).
- [ ] Repeat all checks on the final release commit after remaining audit work.
- [ ] Perform a live Pterodactyl test with a disposable server, then test backup restore before considering production readiness.

## Release gate

Do not publish the `stable` image or deploy the Egg until all critical findings are fixed, the full automated suite and container smoke test pass on the same commit, and a live Pterodactyl installation and restore test have been completed. Discord and voice remain optional later milestones; they must not delay or weaken the core security and recovery release gate.
