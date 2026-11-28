# Disposable Linode acceptance-test runbook

**Purpose:** prepare a short, isolated test of the current Orinoco source on a temporary Linode VPS. This is a standalone Docker Compose test, not a Pterodactyl deployment and not a production installation.

**Approval boundary:** do not create the VPS, allocate billable resources, change firewall/network settings, publish an image or release, or begin a paid test until the owner explicitly approves the exact Linode plan, region, estimated hourly cost and maximum test duration. Credit may offset charges but does not remove the need to confirm the spend.

**Current source target:** `main` at `49549c19043bb17de45f02fb9f897e28e89f64c0` (2026-11-28). Re-check the main branch and CI immediately before the test. If main has moved, record and use the newer commit only after its required checks pass.

## Test objectives

1. Prove a clean Ubuntu 24.04 host can build and start the current Orinoco container from source.
2. Verify the web application, health/readiness endpoints, first-admin bootstrap, login, user separation, diagnostics and support-bundle redaction.
3. Verify persistent data and settings survive a container restart.
4. If resources permit, pull a small local Ollama model and test one English and one Welsh exchange.
5. Record startup time, peak RAM, disk use, model download size/time, response latency and any errors.
6. Shut down and destroy the disposable VPS after results have been reviewed and retained.

This test does not prove production readiness, public HTTPS/reverse-proxy security, Pterodactyl Egg compatibility, Discord/voice operation, or long-term performance.

## Before provisioning

- [ ] Re-check `main` SHA and all required CI check-runs; record the exact SHA.
- [ ] Inspect current Linode/Akamai plan availability, region, hourly rate, disk/network charges and estimated two-hour total.
- [ ] Confirm the remaining credit and expiry in the provider account; do not assume credit covers every charge.
- [ ] Agree the exact instance type, region, spend cap and test window with the owner.
- [ ] Use a fresh instance with no unrelated workloads or personal data.
- [ ] Use SSH key authentication; do not enable password login.
- [ ] Decide whether a firewall is needed for SSH only. Do not open the Orinoco application port publicly.
- [ ] Prepare a secure place to retain test notes and redacted logs. Never copy secrets, prompts, conversations, memories or documents into the report.

**Suggested capacity:** choose a current Ubuntu 24.04 plan with at least 4 vCPU and 8 GiB RAM if the goal includes building the image and trying a small local model in the same session. A smaller plan may be sufficient for app-only checks, but may make image builds or inference slow or memory-constrained. Confirm actual plan pricing and availability before choosing; this runbook does not authorise a particular plan.

## Provisioning and host preparation

Only after the owner approves the exact billable instance:

1. Create a new Ubuntu 24.04 LTS Linode in the agreed region and size.
2. Attach the owner's SSH public key. Record the instance ID, public IP, plan and creation time.
3. Apply provider firewall rules allowing SSH only from the operator's current trusted IP where practical. Do not expose ports 8000 or 11434 publicly.
4. Connect over SSH and confirm the OS release and available resources:

```sh
lsb_release -a
nproc
free -h
df -h
```

5. Update the OS and install Docker Engine plus the Docker Compose plugin using Docker's official Ubuntu instructions. Do not install Pterodactyl, Wings, a reverse proxy or unrelated services.
6. Record the Docker Engine and Compose versions. Confirm there is adequate free disk before building.

## Fetch and build the exact source

Use the exact SHA approved before provisioning. Do not use a mutable image tag and do not publish anything to GHCR.

```sh
git clone https://github.com/lcswolf/orinoco-ai.git
cd orinoco-ai
git checkout 49549c19043bb17de45f02fb9f897e28e89f64c0
git rev-parse HEAD
```

The final command must print the approved SHA. If it does not, stop and investigate.

Create the persistent data directory and environment file:

```sh
mkdir -p data
cp .env.example .env
chmod 600 .env
openssl rand -hex 32
```

Edit `.env` and set:

- `ORINOCO_IMAGE=orinoco:linode-test`
- `ORINOCO_BOOTSTRAP_TOKEN` to the newly generated random value
- `AI_MODEL=qwen2.5:0.5b` for the initial optional small-model test
- `AUTO_DOWNLOAD_MODEL=false` for app-only checks
- `MODEL_CONTEXT=1024`
- `AI_THREADS=0`
- `AUTO_SAVE_MEMORIES=false`
- `ENABLE_WEB_SEARCH=false`
- `ORINOCO_BACKUP_ENABLED=false`

Keep the token out of shell history, screenshots, logs and chat. Do not set an external inference endpoint or any third-party AI API credentials.

Build the image locally from the checked-out source:

```sh
docker build --pull -f docker/Dockerfile -t orinoco:linode-test .
```

This build uses the repository's pinned base image, dependency lock and Ollama installer checksum. It does not publish an image. If the build fails, preserve the relevant redacted build output and stop rather than substituting an older public image.

Find the container's numeric runtime user and set persistent directory ownership:

```sh
ORINOCO_UID=$(docker run --rm --entrypoint id orinoco:linode-test -u)
ORINOCO_GID=$(docker run --rm --entrypoint id orinoco:linode-test -g)
sudo chown -R "$ORINOCO_UID:$ORINOCO_GID" ./data
```

## App-only smoke test

The checked-in `compose.yaml` binds the web port to host loopback only and does not publish Ollama. Keep that boundary.

```sh
docker compose config
docker compose up -d
docker compose ps
docker compose logs --tail=200 orinoco
```

Check the endpoints on the VPS:

```sh
curl -i http://127.0.0.1:8000/healthz
curl -i http://127.0.0.1:8000/readyz
```

With automatic model download disabled, `/readyz` may correctly report that no model is ready. This is expected in app-only mode; it is not an AI inference pass.

For browser access without opening a public application port, create an SSH tunnel from the operator's computer:

```sh
ssh -L 8000:127.0.0.1:8000 <ssh-user>@<vps-ip>
```

Then open `http://127.0.0.1:8000` locally. Use the real SSH username and IP; do not place credentials in the command.

## Application acceptance checks

Record each result as **Pass**, **Fail** or **Not tested**, with a short note.

- [ ] Container starts without a crash/restart loop.
- [ ] `/healthz` returns the expected healthy response.
- [ ] First-admin setup accepts the one-time bootstrap token.
- [ ] Remove the bootstrap token from `.env` after setup and restart the service.
- [ ] Admin can sign in and sign out.
- [ ] Create a standard user; verify it cannot access admin-only controls or diagnostics.
- [ ] Verify CSRF-protected actions behave as expected.
- [ ] Check diagnostics for database, storage and local Ollama status.
- [ ] Download the support bundle as admin and inspect it locally.
- [ ] Confirm the support bundle excludes prompts, replies, memories, documents, credentials, environment values and free-form exception/log messages.
- [ ] Confirm application logs do not expose the bootstrap token or other secrets.
- [ ] Change a non-sensitive setting, restart the container and confirm the setting and accounts persist.
- [ ] Confirm the container runs as its non-root application user.
- [ ] Confirm Ollama is not listening on a public host interface.

Do not use real personal data. Use disposable test accounts and synthetic test messages only.

## Optional local-model and language check

Only proceed after app-only checks pass and actual free RAM/disk have been reviewed.

1. Edit `.env` to set `AUTO_DOWNLOAD_MODEL=true`; retain `AI_MODEL=qwen2.5:0.5b`, `MODEL_CONTEXT=1024` and one-request concurrency.
2. Start/recreate the service and watch memory, disk and logs:

```sh
docker compose up -d
docker compose logs -f --tail=200 orinoco
docker stats --no-stream orinoco
free -h
df -h
```

3. Wait for model initialisation and confirm `/readyz` becomes ready.
4. Send one short English prompt and one short Welsh (`Cymraeg`) prompt. Record latency and manually assess whether each reply uses the requested language. Do not claim language quality from one sample.
5. Stop the model test if memory pressure, disk exhaustion, repeated restarts or host instability occurs. Do not upgrade to a larger model during this first acceptance window.

For a repeatable local evaluation after the VPS test, use `scripts/benchmark_languages.py` against a loopback Ollama endpoint. Its output may contain model prompts and responses; keep it private and redact before sharing.

## Resource and error record

Capture at start, during model download/inference (if attempted), and at end:

- VPS plan, vCPU, RAM, disk and region.
- Exact Git commit SHA and Docker/Compose versions.
- Image build duration and result.
- Container startup duration and restart count.
- RAM usage/peak, swap activity and disk usage.
- Model name, download duration/size and readiness result.
- English/Welsh response latency and manual observations.
- Relevant error messages after removing secrets and personal content.

A simple snapshot can be recorded with:

```sh
date -Is
free -h
df -h
docker stats --no-stream orinoco
docker compose ps
```

This is a one-session baseline only. It does not implement hourly/daily/weekly historical monitoring; that remains a separate product feature.

## Shutdown, evidence and destruction

1. Stop Orinoco cleanly:

```sh
docker compose down
```

2. Retain only the approved redacted test notes and logs needed to diagnose failures. Do not upload the raw `.env`, database, model files, private data or unredacted support bundle.
3. Confirm no containers or unrelated workloads remain:

```sh
docker ps -a
```

4. Review the results with the owner. Do not leave the VPS running while waiting for review unless the owner explicitly approves the additional cost.
5. After explicit confirmation to clean up, destroy the Linode through the provider control panel/API and verify the instance no longer exists.
6. Record the destruction time and final provider billing/credit estimate. Do not assume deleting a VPS also deletes separately retained backups, snapshots, volumes or reserved IPs; check and remove any test resources only with approval.
7. Confirm there are no remaining test resources accruing charges.

## Exclusions

- No access to, changes on, or shutdown of the existing game-server VPS.
- No Pterodactyl Panel or Wings installation in this test.
- No GHCR publishing, image tagging as a release, GitHub release or deployment.
- No public exposure of the Orinoco app or Ollama ports.
- No external AI inference/API provider.
- No Discord or voice acceptance claims.
- No production data, real users or live customer traffic.
- No automatic deletion of retained evidence or provider snapshots without owner approval.
