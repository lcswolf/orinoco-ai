# Orinoco test VPS runbook

**Purpose:** a controlled, temporary first deployment on the existing 2 vCPU / 2 GiB RAM / 40 GB Ubuntu 24.04 Pterodactyl node. The node already has Panel-connected Wings and currently hosts a game server. This is a staging exercise, not a production deployment.

**Safety rule:** do not modify/reinstall Panel, Wings, Docker, node networking, existing allocations or the game server configuration. The game server may be stopped by its owner for the agreed test window, then restarted. Do not run host commands or change node configuration as part of routine Orinoco setup.

## Release gate before the maintenance window

- [ ] The Orinoco image has been built, tagged and published to GHCR, and the exact immutable tag/digest is recorded.
- [ ] The matching `egg/egg-orinoco.json` has been checked against the published image and imported into a dedicated Orinoco Nest.
- [ ] The test owner can access the Pterodactyl administrator UI and has permission to create a test server and assign a free allocation.
- [ ] A free, dedicated TCP allocation is identified. Do not reuse the game server's port.
- [ ] The test server has a separate persistent data directory/volume managed by Pterodactyl. Do not attach or reuse the game server's files.
- [ ] A secure, unique bootstrap token (at least 32 random characters) and backup encryption key are ready to enter as hidden server variables. Keep both in an off-server password manager; never paste them into chat, logs or a startup command.
- [ ] The owner has confirmed the game server can be stopped for the full test window and restarted afterwards.
- [ ] Any provider-level snapshot/backup desired before the test has been taken. This is optional but recommended; do not assume a Pterodactyl server backup protects the whole VPS.

**Do not start the one-hour window while the image is unpublished or the Egg is still marked preview-only.** The current container CI workflow builds and smoke-tests an image but explicitly uses `push: false`; a successful CI build is not a published image that Wings can pull.

## Before stopping the game server

1. Record the node's current RAM, disk usage and running-server list from the Panel/provider dashboard.
2. Confirm which game server will be stopped and notify anyone using it.
3. Record its current startup settings and allocation; do not edit them.
4. Confirm the dedicated Orinoco allocation is free and not assigned to another server.
5. Confirm the Orinoco image tag, Egg JSON and release notes are available to the operator.
6. Prepare the Orinoco test-server settings below, but do not create/start it until the release gate is satisfied.

## Conservative first-run settings

The host has only 2 GiB total RAM, shared with Ubuntu, Docker and Wings. This is materially below the project's 4 vCPU / 6 GB target sizing and is not a supported performance baseline.

| Setting | First application boot | Optional model experiment |
|---|---:|---:|
| Container memory | Start conservatively; leave host headroom | Increase only if measured free RAM allows |
| AI model | `qwen2.5:0.5b` | `qwen2.5:0.5b` |
| Automatic model download | `false` | `true`, after app-only checks pass |
| Model context | `1024` | `1024` |
| AI concurrency | `1` | `1` |
| Automatic memory saving | `false` for initial smoke test | Enable after account/privacy checks |
| Web search | Disabled | Disabled |
| Discord / voice | Disabled | Disabled |
| Backup schedule | Leave disabled or outside the test window | Configure after backup key is verified |

The app-only boot validates container start, Panel console, HTTP health, login/bootstrap and diagnostics without pulling a model. `/readyz` is expected to report model missing while automatic download is disabled; this is not a successful AI inference test. Only attempt the 0.5B model pull after checking actual free RAM and disk. Stop the model experiment if the node becomes unstable or memory pressure appears. Do not try 1.5B or 3B on this 2 GiB staging host.

## One-hour execution plan

### Minute 0–10: make the node quiet and create the isolated server

- [ ] Stop only the agreed game server using its normal Pterodactyl Stop action.
- [ ] Confirm it is stopped; do not delete it or alter its startup configuration.
- [ ] Recheck node RAM/disk and confirm the dedicated allocation is available.
- [ ] Create a new Orinoco test server using the dedicated Nest/Egg, unique server name and separate allocation.
- [ ] Set conservative CPU, RAM and disk limits based on measured node headroom. Do not allocate all host RAM to the container.

### Minute 10–20: first boot and Panel integration

- [ ] Start Orinoco from the Panel.
- [ ] Confirm image pull and container startup succeed.
- [ ] Confirm Ollama and web app supervisor processes start; no repeated crash/restart loop.
- [ ] Confirm the Panel console receives useful logs without credentials or chat content.
- [ ] Confirm `/healthz` responds through the assigned allocation.
- [ ] Confirm `/readyz` reports the expected model-missing state for app-only mode.
- [ ] Stop and start once from the Panel to verify lifecycle handling.

### Minute 20–35: application and diagnostics

- [ ] Complete first-admin setup using the one-time bootstrap token.
- [ ] Immediately clear the bootstrap token in the Panel and restart.
- [ ] Sign in as admin; confirm a normal user cannot access admin-only diagnostics.
- [ ] Run diagnostics and inspect database, storage and Ollama checks.
- [ ] Download the support bundle and verify it contains only safe diagnostic metadata, not prompts, replies, memories, documents, tokens or environment values.
- [ ] Check logs in the Panel console and confirm no raw access URLs or credentials appear.
- [ ] Create a standard user and confirm user/admin separation.

### Minute 35–50: persistence, language and optional model test

- [ ] Set the account reply language to English and test a short English exchange if a model is available.
- [ ] Set Welsh and test a short Cymraeg exchange; record quality manually rather than assuming fluency.
- [ ] Restart the server and confirm accounts/settings persist.
- [ ] If RAM and disk headroom are healthy, enable automatic download for `qwen2.5:0.5b`, restart and watch memory, disk and console output.
- [ ] If the model pull completes, test one short prompt at a time (concurrency remains one). Record cold-start and response times.
- [ ] If model download or inference causes memory pressure, stop the experiment and return to app-only validation.

### Minute 50–60: clean shutdown and restore service

- [ ] Stop Orinoco cleanly from the Panel.
- [ ] Record test results, errors, resource peaks, image digest and Panel/Egg details.
- [ ] Leave Orinoco stopped unless the owner explicitly wants it left running.
- [ ] Restart the original game server from the Panel.
- [ ] Confirm the game server returns to its previous state and allocation.
- [ ] Do not delete the Orinoco test server or its data until logs/results have been reviewed and the owner confirms cleanup.

## Acceptance record

Record each as Pass / Fail / Not tested, with a short note:

- Egg import on Panel 1.13.0
- Image pull by Wings
- Server install and persistent data directory
- Panel start / stop / restart
- Console log visibility and secret redaction
- `/healthz` and `/readyz`
- First-admin bootstrap and token clearing
- Admin-only diagnostics and support bundle
- User/admin permission separation
- Database and settings persistence across restart
- English response
- Welsh response
- 0.5B model pull and one-at-a-time inference (optional)
- Peak RAM, disk used, startup time and response time
- Original game server restored successfully

## Known limitations and exclusions

- This test does not validate public HTTPS, DNS, Caddy/Nginx, Tailscale or production firewall changes. Those are separate host-ingress tasks and must not be improvised during this short staging window.
- This test does not validate Discord or voice; those modules are not ready for live acceptance.
- This test does not establish that the 2 GiB VPS can host Orinoco and the game server concurrently.
- A green GitHub container build is not equivalent to a GHCR-published image or a successful Panel/Wings deployment.
- The current Egg and Panel documentation remain explicitly preview-only until live import, startup, persistence, shutdown and recovery have been verified.
