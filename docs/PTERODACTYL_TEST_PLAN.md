# Orinoco Pterodactyl deployment test plan

**Status: prepared; execution blocked until a disposable test host and matching image are available.**

This runbook is for the first live validation of the Orinoco PTDL_v1 Egg on Pterodactyl Panel 1.13.0. It is deliberately separate from the automated container smoke test: CI can validate the image and scripts, but it cannot prove that a real Panel, Wings daemon, allocation, server volume, proxy or host behaves correctly.

Do not use a production server or real personal data for this rehearsal. Do not publish an image or deploy to a public VPS as part of repository preparation.

## 1. Entry criteria

Do not begin the live test until every item below is true:

- [ ] A disposable Linux host is available with a supported Pterodactyl Panel 1.13.0 and Wings installation.
- [ ] The exact Orinoco image under test has been built and made available to that host. The current Egg references `ghcr.io/lcswolf/orinoco-ai:stable`, but that tag must not be assumed to exist or to match the source commit.
- [ ] The image's source commit, image digest and build/smoke workflow run are recorded.
- [ ] The Egg JSON has been imported into a dedicated test Nest and reviewed before server creation.
- [ ] A spare allocation is available and its port is recorded.
- [ ] A unique backup encryption key has been generated using the documented CLI and stored outside the test server. Never commit it or paste it into an issue or log.
- [ ] The test operator has a way to access the Panel, Wings logs and host/container logs.
- [ ] The test server contains no valuable user data. Confirm that deleting the test server and its volume is acceptable.

If the Panel, Wings or image is not ready, stop here. Do not work around an unavailable image by silently substituting a different tag.

## 2. Import and create the test server

1. Record the Panel version and Wings version.
2. Import `egg/egg-orinoco.json` into a dedicated test Nest.
3. Confirm the Egg is recognised as PTDL_v1 and that all variables render with the intended defaults and descriptions.
4. Check that the image reference matches the exact image digest selected for this rehearsal.
5. Create a disposable server using the Egg and assign one available allocation.
6. Set the required backup encryption key through the Panel's protected variable interface. Do not place the key in startup commands or public notes.
7. Keep the default curated model at `qwen2.5:1.5b`, automatic model download enabled, context 2048 and concurrency 1 for the first baseline.
8. Record the server UUID, allocation, image digest and configuration with secrets redacted.

**Pass condition:** Egg imports without schema errors; server is created with the intended image, startup command, variables and allocation. No secret is exposed in the normal user-visible variable list or logs.

## 3. Install, start and network access

- [ ] Installation script completes successfully and creates the expected persistent data directories.
- [ ] First start launches Supervisor and all expected programs.
- [ ] The web service binds to the allocated `SERVER_PORT` on `0.0.0.0`.
- [ ] The application responds on the host's public IP and allocated port, using HTTP only for this isolated initial connectivity check.
- [ ] `/healthz` reports liveness.
- [ ] `/readyz` reports not-ready while the model is absent or still downloading, then ready after model initialisation succeeds.
- [ ] The browser can sign in and complete a basic chat request after the model is ready.
- [ ] Stop and start the server through the Panel; confirm the service returns without manual shell intervention.
- [ ] Restart the container and confirm the selected model and application data persist.

Record the exact allocation and the externally observed URL. Direct IP-and-port access is a required product path; do not treat a working subdomain as a substitute.

## 4. Model download and failure recovery

- [ ] With automatic download enabled, observe the selected allowlisted model being downloaded to persistent model storage.
- [ ] Confirm Ollama listens only on container loopback at `127.0.0.1:11434`; it must not be exposed through the Pterodactyl allocation.
- [ ] Confirm cloud features are disabled and no external inference provider is contacted.
- [ ] Complete a short chat prompt and verify a response is generated locally.
- [ ] Restart the server and confirm the model is reused rather than downloaded again.
- [ ] On a separate disposable run, test a deliberately invalid/unavailable model setting and confirm startup fails visibly without an infinite restart loop.
- [ ] On another disposable run, interrupt model download or temporarily make the model registry unavailable; confirm bounded retries, clear logs and recoverability after the underlying issue is fixed.

Do not simulate failures on a server containing data that must be retained.

## 5. Persistent data and account isolation

- [ ] Confirm the SQLite database is stored under the server volume, not in an ephemeral container layer.
- [ ] Confirm model weights, private documents and backups are stored under the expected persistent data directories.
- [ ] Create two test accounts and verify conversations, memories and private documents remain isolated.
- [ ] Restart the container and verify both accounts' test data remains available.
- [ ] Confirm the container runs as a non-root user and application code is not writable by the runtime account.
- [ ] Confirm Ollama's API port is not reachable from outside the container.

Use synthetic test data only. Delete the test accounts and files after the rehearsal.

## Panel-first operations acceptance

The operational goal is to manage Orinoco through Pterodactyl Panel and the Orinoco web interface, without SSH or Docker commands after the VPS, Panel and Wings infrastructure is ready. See [Panel-first Management](PANEL_MANAGEMENT.md).

- [ ] Create the first administrator using the browser setup flow armed from a hidden Panel variable; no SSH, Docker exec, TTY or password in console logs.
- [ ] Confirm first-run setup refuses a second bootstrap after an account exists and the bootstrap token is invalidated after success.
- [ ] Recover a locked-out administrator using the documented Panel-first recovery flow; confirm it is single-use and revokes existing sessions.
- [ ] Generate and configure the backup encryption key without printing it to persistent Panel console logs; retain an off-server copy.
- [ ] Change supported Egg variables in the Panel and confirm the running service applies them after restart.
- [ ] Use the Panel console and file manager for normal logs and file operations without shell access.
- [ ] Run backup, verification, restore, migration and rollback using the documented Panel maintenance workflow; confirm the server returns to normal startup afterwards.
- [ ] Confirm every routine operational step in the user guide can be completed without SSH or Docker commands.
- [ ] Record any remaining host-level SSH task separately as infrastructure provisioning, not Orinoco application administration.

## 6. Backup, restore and update recovery

- [ ] Generate a local encrypted backup through the documented CLI.
- [ ] Verify the backup using the same protected key.
- [ ] Confirm the backup contains the database and document data, but does not contain model weights.
- [ ] Copy one encrypted backup off the test host through an approved secure method.
- [ ] Stop the application and rehearse restore into a disposable data volume.
- [ ] Verify account data, conversations, memories and documents after restore.
- [ ] Test a deliberately invalid backup and confirm it is rejected without damaging live data.
- [ ] Rehearse the documented update path with a pre-migration backup.
- [ ] On a disposable copy only, inject a migration/post-check failure and verify rollback or the documented manual recovery instructions.
- [ ] Confirm the backup key is available independently of the VPS and is not stored only on the server being backed up.

Record restore duration, backup size, result and any manual steps. A backup that has never been restored is not yet proven recoverable.

## 7. Proxy, TLS and private access

Run these checks only after the direct allocation test passes:

- [ ] Configure the documented reverse-proxy topology and verify the public domain over valid HTTPS.
- [ ] Verify HTTPS access through the public IP on the documented alternate port, if that access path is enabled for the test.
- [ ] Confirm proxy request-body limits, login/chat rate limits and model timeout behaviour.
- [ ] Measure the actual connecting proxy peer address from inside the Orinoco container before setting `ORINOCO_TRUSTED_PROXY_IPS`.
- [ ] Confirm spoofed `X-Forwarded-For` values from an untrusted peer do not change the observed client address.
- [ ] Verify Tailscale Serve access is tailnet-only and that Funnel/public exposure is not enabled.
- [ ] Confirm the Ollama port and internal application port are not accidentally exposed by host firewall or proxy rules.

Do not guess the trusted proxy address or copy an example address into production configuration.

## 8. Resource and operational checks

Record CPU, memory and disk use during first model download, idle operation and a short chat session.

- [ ] Confirm the selected model can load within the configured memory limit.
- [ ] Confirm disk space is sufficient for the model, database, documents and backup retention.
- [ ] Confirm the daily backup scheduler starts and reports its status.
- [ ] Confirm backup retention does not prune old backups after a failed backup or failed required remote upload.
- [ ] Confirm logs are visible in the Panel console and do not contain passwords, session cookies, backup keys or private document contents.
- [ ] Stop/restart the server and verify child processes are terminated cleanly.

The planned small VPS is a constrained target. If memory pressure, OOM termination or disk exhaustion occurs, record the exact configuration and measurements; do not increase resource assumptions without checking the hosting budget.

## 9. Browser and accessibility checks

Use the manual browser matrix in [PRE_RELEASE_AUDIT.md](PRE_RELEASE_AUDIT.md) after the app is reachable. Test on real iOS Safari and Android Chrome devices as well as desktop Chrome, Firefox and Edge. Record OS/browser versions, viewport sizes, keyboard/screen-reader checks and defects.

## 10. Evidence and sign-off

Complete this table during the rehearsal:

| Field | Result |
|---|---|
| Date and operator | Pending |
| Panel version | Pending |
| Wings version | Pending |
| Host OS / architecture | Pending |
| Orinoco source commit | Pending |
| Container image digest | Pending |
| Egg import | Not run |
| Server install/start/stop | Not run |
| Direct IP and port | Not run |
| Model download and local chat | Not run |
| Persistent volume | Not run |
| Backup and restore | Not run |
| Public HTTPS proxy | Not run |
| Tailscale-only access | Not run |
| Browser/device matrix | Not run |
| Outstanding defects | Pending |

A live test is complete only when each applicable check has evidence and failures have been fixed and retested. Keep this document updated with the actual versions, outcomes and links to non-secret logs. Do not mark a check passed based only on source inspection or CI.

## 11. Teardown

1. Export the non-secret test evidence.
2. Revoke temporary credentials and remove test accounts.
3. Delete the disposable Pterodactyl server and its volume after confirming no evidence or backup is still needed.
4. Securely remove the test backup key and any temporary credentials according to the operator's retention policy.
5. Confirm no temporary public image tag, firewall opening, DNS record or proxy route remains unintentionally enabled.
