# Orinoco pre-release audit

**Status: in progress — do not deploy to a public VPS yet.**

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

### Documentation accuracy — corrected

The README and development guide now distinguish implemented encrypted backup operations from the outstanding scheduler/retention work. The Egg's web-search descriptions now reflect the implemented SearXNG integration rather than describing it as future work.

## Remaining review work

- [ ] Finish authentication/session review, including rate-limit behaviour, cookie/proxy assumptions, secret rotation and revocation.
- [ ] Review all database functions and schema evolution for safe upgrades from an existing installation.
- [ ] Review private/shared document ownership, file permissions, extraction limits, archive handling and cleanup failure paths.
- [ ] Review the complete chat flow, memory extraction filters, prompt boundaries, queue handling and failure recovery.
- [ ] Complete SSRF and redirect tests for public webpage fetching; review SearXNG endpoint configuration and returned links.
- [ ] Review encrypted backup archive validation, restore atomicity, rollback copies, key handling and remote transfer failure behaviour.
- [ ] Implement and test automatic daily backups, retention and clear failure reporting.
- [ ] Validate the Egg against the target Panel 1.13.0 format and confirm every environment variable matches the runtime.
- [ ] Validate container startup ordering, process failure handling, writable persistent paths and model-download behaviour.
- [ ] Review frontend XSS exposure, accessibility, keyboard navigation, mobile layout and API error states.
- [ ] Review CI workflow permissions, dependency versions, build reproducibility and vulnerability scanning.
- [ ] Run the complete test suite after all audit corrections; build and smoke-test the final image.
- [ ] Perform a live Pterodactyl test with a disposable server, then test backup restore before considering production readiness.

## Release gate

Do not publish the `stable` image or deploy the Egg until all critical findings are fixed, the full automated suite and container smoke test pass on the same commit, and a live Pterodactyl installation and restore test have been completed. Discord and voice remain optional later milestones; they must not delay or weaken the core security and recovery release gate.
