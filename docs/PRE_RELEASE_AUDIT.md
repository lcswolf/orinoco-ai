# Orinoco pre-release audit

**Status: in progress — do not deploy to a public VPS yet.**

Latest completed GitHub Actions Python test run [#913](https://github.com/lcswolf/orinoco-ai/actions/runs/45611868448) passed on commit `82794c80`: **247 tests passed**, with two Starlette deprecation warnings. Dependency auditing and frontend JavaScript syntax checks also passed. Container build and smoke test [#392](https://github.com/lcswolf/orinoco-ai/actions/runs/45611660714) passed on runtime commit `035f894e`, including shell validation, Pterodactyl Egg JSON validation, Caddy/Nginx template validation, image build and service smoke checks. Egg startup/image, listener-boundary, proxy-trust and model-download retry regression checks passed; live Pterodactyl import, deployment and recovery drill remain outstanding.

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
- Pterodactyl 1.x PTDL_v1 Egg schema, Panel 1.13.0 import compatibility, startup command, variables, allocations and resource assumptions.
- Frontend behaviour, accessibility, responsive layout and safe rendering of untrusted text.
- CI coverage, dependency health, comments/docstrings and user-facing documentation.

## Authentication review — repository checks complete

### Username lockout denial-of-service — corrected

The first login throttle keyed failed attempts globally by username, which allowed a remote client to lock a known account. The username bucket was first scoped to the observed username/client pair, but the planned reverse-proxy topology exposed a second issue: with Uvicorn proxy-header handling disabled, every visitor could appear to the app as the same Nginx peer. The login route now uses forwarded client IPs only when the connecting peer matches the administrator-only `ORINOCO_TRUSTED_PROXY_IPS` allowlist, and accepts only one address from that header. In production, an empty allowlist disables application per-client buckets until the real proxy peer is measured; Nginx's per-client limits are mandatory during that period. Regression tests cover trusted, untrusted, missing and chained forwarding headers. The trackers remain process-local, so the edge proxy must enforce shared limits across workers or replicas.

Repository review confirms signed, HTTP-only, SameSite=Lax and Secure-by-default session cookies; CSRF protection on browser mutations; session rotation after login and password change; account-version invalidation after password or account-status changes; bounded login-failure trackers; and persistent owner-only session-secret storage with symbolic-link rejection. Regression coverage includes login/logout, CSRF, throttling, proxy-header trust boundaries, password-change revocation, suspend/reactivate revocation and secret-file permissions. The remaining authentication work is operational: measure and allow-list the real proxy peer, rehearse session-secret rotation and SSH/container recovery, and decide whether application MFA is required before public multi-user access.

## Confirmed findings and corrections

### First-admin bootstrap command — corrected

The repository contained both `orinoco/admin.py` and the `orinoco/admin/` package. Python resolves the package for `python -m orinoco.admin`, so the documented first-admin command did not execute the standalone module. The command is now implemented by `orinoco/admin/__main__.py` and `orinoco/admin/cli.py`. The CLI also resolves and passes the configured database path explicitly, so the documented `ORINOCO_DATABASE_PATH` override is respected.

A regression test has been added for the bootstrap command and its selected database path.

### Duplicate memory route implementation — corrected

There were two implementations of the same `/api/memories` routes. The application registered the plural `orinoco.memories.routes` implementation; the unused singular `orinoco.memory.routes` implementation has been removed. The singular package remains only for shared compatibility helpers.

### Database docstrings — corrected

Several database function docstrings had been placed inside conditionals or transaction blocks, where Python did not recognise them as function docstrings. They have been moved to the correct function positions to improve maintainability and generated help/documentation.

### Pterodactyl Egg variable validation — tightened

The Egg allowed `ORINOCO_MAX_REQUEST_BODY_BYTES` values below 1 KiB even though the application deliberately treats those values as a server misconfiguration. Its minimum is now 1024 bytes, matching runtime validation, with a regression assertion. The backup encryption key is now required at server creation so the always-on scheduler cannot silently run without the key needed to create encrypted backups. The SearXNG endpoint is hidden and administrator-only because it controls an outbound network destination. These changes are covered by Egg-definition tests; live Panel 1.13.0 import validation remains outstanding.

### Version-aware backup schema validation — strengthened

Backup verification now checks the required preference/persona tables for schema v6 and later, and the v7 automatic-memory preference column for schema v7. It deliberately continues to accept valid v5 snapshots because the application's schema upgrade is additive and creates the later tables on first start. Regression tests cover both a damaged v7 snapshot and a valid v5 snapshot. CI confirmation is pending.

### Backup database verification — strengthened

SQLite can return `ok` from `PRAGMA integrity_check` for an empty database. Backup verification and restore now also require the essential Orinoco tables, reject a database schema newer than the running build, and run `PRAGMA foreign_key_check`. This prevents an empty or structurally inconsistent SQLite file from being accepted as a usable backup. Regression tests cover empty databases, future schema versions and orphaned foreign-key rows.

### Encrypted archive path validation — regression coverage expanded

Regression tests now exercise path traversal, Windows drive/backslash path syntax, symbolic-link archive members and duplicate archive paths using validly encrypted test archives. The extraction code rejects these entries before writing them into the temporary restore directory. The tests still need to pass in CI before this audit item can be marked complete.

### Remote backup verification — strengthened

The first S3-compatible upload implementation checked object size and client-supplied SHA-256 metadata. Metadata alone does not prove the bytes stored by the remote service match the source. Upload verification now downloads the stored object and hashes the returned bytes as well. Symbolic-link backup sources are rejected before resolving the path. Regression tests cover altered remote bytes and symbolic-link inputs.

### Document deletion and storage path handling — strengthened

Private and shared document deletion now removes the original file before deleting its database record. If file cleanup fails, the record remains visible and the user/administrator receives an error so cleanup can be retried; failures during upload rollback are logged. Stored paths reject traversal, final-component symbolic links and a symbolic-link document root. Upload, deletion, backup and restore operations share a cross-process file lock so a backup cannot snapshot database metadata and document files from opposite sides of an in-progress file operation. The lock uses POSIX flock on the Linux VPS and an msvcrt byte-range fallback for Windows development.

### Document storage cleanup and workbook handles — strengthened

The XLSX extraction path now closes its read-only workbook even when parsing fails. Document storage also removes a temporary upload file if writing or the final atomic rename fails, without deleting a pre-existing temporary path it did not create. Regression tests cover both failure paths so interrupted uploads do not accumulate unregistered files and malformed workbooks do not retain open ZIP handles.

### PDF decompression and extraction limits — strengthened

The PDF parser's default decompression ceilings were too generous for the planned small VPS, and the previous extraction path accumulated all page text before truncating it. The pypdf minimum dependency is now 6.13 so its documented stream limits are available. Orinoco lowers filter output limits to 8 MiB per stream, rejects pages with more than four content streams or more than 32 MiB of combined decoded page content, retains the 100-page cap, and stops retaining text after 200,000 characters. Regression tests cover stream-count rejection, bounded text accumulation and the lower decompression settings. The upstream pypdf documentation specifically warns that parsing a large uncompressed page stream can consume many gigabytes of memory and recommends bounding content streams ([extraction guidance](https://pypdf.readthedocs.io/en/stable/user/extract-text.html), [security limits](https://pypdf.readthedocs.io/en/6.13.0/user/security.html)).

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

When a reliable client address is available, the failed-login tracker applies rolling windows per username/client pair and per client address, has fixed memory bounds for both maps, and reports the remaining Retry-After window. In production with no trusted-proxy allowlist, the app skips these client buckets rather than treating a shared proxy address as every visitor; Nginx per-client limits are mandatory. After measuring the Nginx peer inside the container, configure only that peer in `ORINOCO_TRUSTED_PROXY_IPS`. The trackers remain process-local, so edge limits must be shared across workers or replicas.

### Browser security headers — added

The application now sends a restrictive Content Security Policy, clickjacking protection, MIME sniffing protection, a conservative referrer policy, same-origin resource/opener policies and a Permissions Policy disabling unused camera/microphone/geolocation access. The current frontend uses DOM node creation and textContent for dynamic content rather than HTML string injection. Regression tests check the headers on application, API and static responses.

### SQLite schema version safety — strengthened

The database initializer now completes the known additive v1–v5 table/index and session-version upgrades plus v6 per-user response-preference and administrator-persona tables, plus v7 per-user automatic-memory preference. It refuses to modify a database with a newer schema version instead of silently resetting its version number. Regression tests cover additive schema upgrades without losing accounts or defaults, plus refusal to modify a future-version database. Non-additive schema changes will still require an explicit migration before the schema version is increased.

### Local inference boundary — hardened

The production Ollama client and readiness check now use the fixed loopback endpoint. Environment variables and explicit production client URLs cannot redirect prompts to an external inference service; HTTP proxy environment variables are also ignored for Ollama traffic. Only tests that inject a mock transport may use a non-loopback URL. This enforces the agreed local-inference-only architecture.

### Timezone and inactive Egg options — corrected

The runtime now installs the operating-system timezone database so the configured Europe/London timezone is available to Python and scheduled operations. The Discord and voice Egg toggles are now locked off until those integrations actually exist, preventing a server owner from enabling non-functional features.

### Runtime and CI version pins — checked

The Docker image's Ollama pin, `0.40.18`, matches the latest non-prerelease release published on 24 November 2026 ([official Ollama release](https://github.com/ollama/ollama/releases/tag/v0.40.18)). The GitHub Actions workflows use Node 24-compatible releases ([checkout v7.0.1](https://github.com/actions/checkout/releases/tag/v7.0.1), [setup-python v7.1.0](https://github.com/actions/setup-python/releases/tag/v7.1.0), [setup-buildx v4.4.1](https://github.com/docker/setup-buildx-action/releases/tag/v4.4.1), [build-push v7.4.0](https://github.com/docker/build-push-action/releases/tag/v7.4.0)). The latest completed Python suite passes 247 tests (run #913 on `82794c80`), including the bounded model-download retry contract and migration-failure recovery regression. The dependency audit reports no known vulnerabilities and the frontend JavaScript syntax check passes. Two Starlette/httpx deprecation warnings remain; they do not currently fail tests. Container build and smoke test run #392 passed on runtime commit `035f894e`; it includes shell, Egg JSON, proxy-template validation, image build and startup/service smoke checks. The final release gate will repeat the full suite and container smoke test on the same release commit.

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

A dedicated Supervisor-managed process completes at most one successful backup cycle per local calendar day (03:00 by default in the configured timezone). It creates an encrypted local backup, optionally uploads and byte-verifies it to the configured S3-compatible bucket, and prunes expired local backups only after the complete backup cycle succeeds. Failed or interrupted attempts remain retryable and are retried after a 15-minute backoff; a day is not marked complete until the cycle succeeds. The default local retention is 14 days and is configurable from 1 to 365. Failures are written to the Pterodactyl console and a private status JSON file. Remote bucket lifecycle retention and restore-from-remote convenience remain outstanding.

### Post-migration relational integrity — strengthened

The one-shot migration command now runs both SQLite's structural `integrity_check` and `foreign_key_check` after applying schema changes. A migration is not reported as successful if it leaves orphaned conversations, messages, memories or documents. A regression test injects an orphaned conversation after schema initialisation and confirms the command fails closed. This regression test passed in GitHub Actions run #913 (247 tests total).

### Backup-gated update migrations — implemented

The `orinoco.updates` one-shot CLI creates and verifies a fresh encrypted pre-update backup, uploads it when S3 is configured, and requires a verified backup before applying the additive SQLite migrations to an existing database. If migration or post-migration integrity checks fail, it now attempts to restore that verified backup automatically while Orinoco is stopped; if the restore also fails, the command clearly directs the operator to manual recovery. The failure-injection regression passed in GitHub Actions run #913. The operator runbook documents this behaviour. Automated image switching and a live upgrade/rollback drill remain outstanding.

### Document storage symlink parents — hardened

Document writes and path resolution now reject symbolic links in every directory component, not only the final file or configured document root. This closes a path-redirection case where a symlinked per-user or shared-library directory could send a new upload outside the intended storage tree. Regression tests cover a symlinked user directory and a symlinked parent that points back inside the root; the current 242-test CI suite passed.

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
approximately 11 MiB upload-route limit. The document quota lock is an OS-level file lock and serialises processes sharing the same filesystem; multi-host replicas still require verified shared-lock semantics or atomic database quota reservations.

### Personal memory storage — bounded

Each account now has a configurable personal-memory count cap (100 by default, 1–1000 in the Egg). The count check and insert are one SQL statement to avoid concurrent requests exceeding the allowance. Manual creation returns HTTP 409 when full; automatic extraction skips new entries without failing a successful chat. Regression tests cover per-user isolation and the full-quota chat path.

### Chat generation queue — bounded

The chat API now reserves one of a bounded number of in-flight slots before loading account context. The default is one model-generation slot plus eight additional admitted requests; excess requests receive HTTP 503 and `Retry-After: 5`. The additional capacity is configurable from 0–32 in the Egg. A regression test verifies overload rejection and slot release. This limiter is process-local; a multi-worker deployment needs shared queue coordination.

### Reverse-proxy design — documented, not yet deployed

The network plan now documents Caddy public TLS, Nginx loopback-only request/body/rate/connection limits, the public HTTPS subdomain, short-lived IP certificate access on port 8443, and tailnet-only Tailscale Serve on port 8444 without Funnel. Uvicorn is explicitly started with forwarded-header processing disabled until the real proxy peer address can be measured and allow-listed. The live Leaseweb/Pterodactyl host, Docker published-port firewall path, certificate issuance/renewal, actual client IP handling and all three access paths still require verification. See `docs/NETWORK_DEPLOYMENT.md`.

### First-run model download recovery — improved

The startup audit found that a failed first-run Ollama pull was attempted only once. The model-init process then exited while the web interface remained alive and correctly reported model readiness as HTTP 503. A transient registry/network failure would therefore require an operator restart. Model initialization now retries the curated model pull up to three times, waiting 30 seconds between failures; exhaustion logs an explicit error and leaves readiness false rather than claiming the model is available. A regression check protects the retry limit, delay and failure message. The selected model and user data remain under the persistent /home/container/data volume; Ollama model weights are intentionally excluded from encrypted backups to avoid very large backup files. Live Supervisor restart timing and a failed-download recovery rehearsal remain part of the disposable Panel test.

## Remaining review work

- [x] Add administrator-managed core persona and humour controls plus private per-user response voice, tone and answer-detail preferences, including persistence, API authorisation and prompt integration.

- [x] Add bounded per-client-address login throttling alongside per-username limits.
- [x] Add owner-only SQLite file permissions and symbolic-link rejection.
- [x] Complete repository-level authentication/session review: login/logout, CSRF, session rotation/version invalidation, login throttling, trusted-proxy parsing and persistent secret-file handling are covered by regression tests. Live trusted-proxy configuration, session-secret rotation and SSH/container recovery rehearsals remain deployment gates; application MFA remains an open decision for public multi-user access. Application-level declared-body limits and configurable per-user/shared document quotas are implemented; reverse-proxy limits (including chunked requests), multi-host shared-storage quota semantics and chat retention remain outstanding.
- [x] Add regression coverage for legacy v1/v5 additive schema upgrades and refusal of newer or negative schema versions.
- [x] Harden SQLite persistence: private parent directory, owner-only regular database file, production fail-closed permissions, symlink/non-regular rejection and path-identity checks.
- [ ] Rehearse database migration and rollback against a real Pterodactyl data volume; finish any remaining query/data-isolation edge cases.
- [x] Add bounded Office ZIP expansion checks and regression coverage.
- [x] Preserve retryable document records when file deletion fails and reject unsafe stored paths.
- [x] Complete repository-level review of private/shared document ownership, parser limits and cleanup paths. Regression coverage verifies private-user isolation, shared-library read/delete permissions, per-user quotas, upload rollback cleanup, retryable deletion failures, traversal/symlink rejection, Office archive expansion limits, PDF stream/page/text limits and XLSX handle closure. Configure and live-test an approximately 11 MiB reverse-proxy request-body limit for document upload routes (and global limits for other routes) so oversized and chunked multipart bodies are rejected before application parsing.
- [x] Bound model prompts to the configured context: preserve system/current messages, trim older history/reference data, and return HTTP 422 when the current request cannot fit (covered by context-budget tests).
- [x] Review the chat flow, memory extraction filters, prompt boundaries, queue admission and failure recovery at repository level. Chat history, memories and document search are account-scoped; web search is explicitly opt-in per message; retrieved text is labelled untrusted; generation capacity is bounded; model failures do not save a failed exchange; and memory-extraction failures do not discard a successful reply. Memory candidates are limited to three short durable facts and filtered for sensitive data, contact details and instruction/prompt-injection patterns. Regression coverage exists for per-user memory/document context, opt-out, unsafe memory candidates, overload rejection and recovery. Remaining deployment concerns are process-local queue/rate trackers and live reverse-proxy enforcement.
- [x] Complete SSRF and redirect tests for public webpage fetching; review SearXNG endpoint configuration and returned links.
- [x] Strengthen restore rollback for the database, WAL state and file-based session secret.
- [x] Confirm CI passes the latest backup database/archive/WAL/scheduler, PDF parser, document-cleanup, trusted-proxy, SQLite permission/path, mobile accessibility and Egg regression tests (Python run #849; container build/smoke #376).
- [x] Implement and test automatic daily encrypted backups, local retention and failure reporting.
- [ ] Configure remote bucket lifecycle retention and convenient restore-from-remote.
- [x] Add backup-verified pre-update and explicit database migration commands plus a Pterodactyl operator runbook.
- [x] Add automated checks that active Egg environment variables are referenced by runtime code and that persistent install/model/database paths align (run #898).
- [ ] Import the Egg into a live disposable Panel 1.13.0 instance and verify server startup and allocation wiring; automated JSON checks do not replace this live compatibility test.
- [ ] Apply and live-test the Caddy/Nginx/Tailscale design in [Network Deployment](NETWORK_DEPLOYMENT.md): public HTTPS subdomain, HTTPS IP:8443, private Tailscale Serve :8444 (no Funnel), Docker/Wings firewall restrictions, edge body/rate/connection limits and certificate renewal.
- [ ] Decide whether host-level full-disk or dedicated-volume encryption is required for the live SQLite database and uploaded documents; document the unlock and recovery process before storing sensitive material.
- [x] Review container startup ordering, process failure handling, writable persistent paths and model-download behaviour at repository level. First-run model pulls now retry transient failures three times with a 30-second delay; after exhaustion the model-init process exits with a clear console error and /readyz remains HTTP 503. The web process may still serve the interface while the model is unavailable. Live Supervisor/Pterodactyl startup and failure-recovery behaviour remains to be exercised on a disposable server
- [x] Add restrictive browser security headers and verify they apply to application/API/static responses.
- [x] Validate external links and render untrusted search/document/chat text without HTML parsing.
- [ ] Browser-test the accessible mobile navigation drawer, focus trapping, narrow topbar and API error states on iOS, Android and desktop. Static regression checks now cover ARIA state, inert background content, Escape/Tab handling and focus-visible styling.
- [x] Integrate the original Womble-inspired Orinoco mascot, accessible SVG artwork and UK woodland visual treatment.
- [x] Add weekly Dependabot monitoring for Python and GitHub Actions dependencies.
- [x] Add pip-audit to CI and resolve the reported cryptography advisories; the follow-up audit is clean.
- [ ] Continue reviewing dependency updates and build reproducibility.
- [x] Confirm the latest Python test suite, dependency audit and frontend JavaScript syntax checks passed on commit `82794c80` (run #913; 247 tests).
- [x] Confirm the container build and smoke test passed on runtime commit `035f894e` (run #392); image remains unpublished.
- [ ] Repeat all checks on the final release commit after remaining audit work.
- [ ] Perform a live Pterodactyl test with a disposable server, then test backup restore before considering production readiness.

## Release gate

Do not publish the `stable` image or deploy the Egg until all critical findings are fixed, the full automated suite and container smoke test pass on the same commit, and a live Pterodactyl installation and restore test have been completed. Discord and voice remain optional later milestones; they must not delay or weaken the core security and recovery release gate.
