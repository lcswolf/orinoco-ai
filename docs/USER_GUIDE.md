# Orinoco AI User and Setup Guide

**Status: preview guide.** Orinoco's application and container are under active development. The Docker image has not been published and the Pterodactyl Egg has not yet been imported and tested on a live Panel. Use this guide for planning and for a future test installation only; do not treat the steps as a production-ready deployment until the release gate in [Project Status](PROJECT_STATUS.md) is cleared.

This guide is intended to cover the complete user journey. The operating goal is Panel-first management: after the VPS, Pterodactyl Panel and Wings are ready, routine Orinoco setup and operation should not require SSH or Docker commands. See [Panel-first Management](PANEL_MANAGEMENT.md) for the requirements and current gaps.

## 1. What you need

For the planned first installation:

- A Linux VPS with a public IPv4 address. The current sizing plan is 4 vCPU, 6 GB RAM and 100 GB NVMe; this is a target to test, not a validated minimum.
- Ubuntu 24.04 LTS on the host.
- Pterodactyl Panel 1.13.0 (stable 1.x) and a working Wings node.
- A Pterodactyl allocation for Orinoco's web interface.
- A domain name if you want the public HTTPS subdomain.
- A provisioned Pterodactyl host and node. Initial Ubuntu, Panel/Wings and host-network provisioning may still require infrastructure-level access; routine Orinoco management is intended to use the Panel.
- A secure place away from the VPS to store the backup encryption key.

Orinoco runs its language model locally through Ollama. The first launch downloads the selected model, so allow time and disk space for the model and its cache. The initial model choices are Qwen 2.5 0.5B, 1.5B and 3B. The 1.5B model is the recommended starting point for the planned VPS; 3B is experimental at this memory size.

## 2. Prepare the host and network

1. Install and secure the Ubuntu host, then install/configure Pterodactyl Panel and Wings using their official instructions.
2. Confirm the node can create and start an ordinary test server and that the chosen allocation is reachable from the host.
3. Follow [Network Deployment](NETWORK_DEPLOYMENT.md) to configure the planned Caddy public TLS endpoint, Nginx loopback edge and Tailscale private access.
4. Choose and record the access path you will test:
   - Public domain: `https://YOUR_DOMAIN/`
   - Public IPv4: `https://YOUR_PUBLIC_IPV4:8443/`
   - Private tailnet URL: `https://YOUR_SERVER.TAILNET.ts.net:8444/`
5. Apply the host firewall so only the required public ports are exposed. Keep the Nginx edge listener loopback-only, keep Ollama private, and do not expose the container's raw allocation directly as a permanent public endpoint.

The sample proxy files are templates. Replace example domains, addresses and allocation ports, validate the configuration, and verify the real client IP before relying on proxy rate limits. Do not copy a template onto a live host without reviewing it.

## 3. Import the Orinoco Egg

Do this only after a release image has been published and its release notes say it is ready for testing.

1. In Pterodactyl, open **Admin → Nests** and create a dedicated **Orinoco AI** Nest.
2. Import `egg/egg-orinoco.json` from this repository.
3. Create a server using the imported Orinoco Egg.
4. Select the exact Docker image tag named in the release notes. Do not guess a tag or rely on an unpublished `:stable` image.
5. Assign the web allocation and enough disk/RAM for the model and persistent data.
6. Set the required backup encryption key and review the other Egg variables before starting.
7. Start the server and watch the console for Ollama startup, model download and web-service readiness messages.

The live import, first start, image pull, and Pterodactyl console behaviour are still release-gated and must be tested on a disposable server first. Detailed Egg notes are in [Pterodactyl Egg](PTERODACTYL_EGG.md).

## 4. Configure Orinoco

The following are the main settings currently exposed by the preview Egg.

| Setting | What it does | Suggested initial value |
|---|---|---|
| AI Model | Local Ollama model | `qwen2.5:1.5b` |
| Automatically Download Model | Pull model into persistent storage on first start | `true` |
| Model Context | Context length used for requests | `2048` |
| Automatically Save Memories | Allow extraction of useful non-sensitive memories; users can manage their own memories | `true` |
| Enable Web Search | Enable the SearXNG research feature | `true` only when configured |
| SearXNG URL | Administrator-configured search service endpoint | Blank until configured |
| Timezone | Timezone used by services and backup schedule | `Europe/London` |
| Backup Encryption Key | Key for encrypted backups | Required; generate and store securely |
| Daily Backup Time | Local time for scheduled backup | `03:00` |
| Local Backup Retention | Days of local backup retention | `14` |

Keep the Discord and voice settings disabled. These integrations are not implemented yet.

### Generate and protect the backup key

After signing in as an administrator, open **Account settings → Backup encryption key** and choose **Generate backup key**. Orinoco uses the browser's cryptographically secure random-number generator to create a 256-bit URL-safe base64 key. The key is generated locally in the browser: it is not sent to the Orinoco server, saved in browser storage or written to logs.

1. Use the **Copy key** button and store the key in a password manager or another secure location away from the VPS.
2. In Pterodactyl, paste it into the hidden `ORINOCO_BACKUP_KEY` server variable.
3. Restart Orinoco so the service reads the new variable.
4. Return to the browser and use **Clear key**. Closing the settings dialog also clears the displayed value. Do not leave the key displayed on a shared device.

The browser generator requires a modern browser with `crypto.getRandomValues`. It also works when Orinoco is accessed directly by IP and port over HTTP; if automatic clipboard access is unavailable, the key is selected for manual copying. HTTPS is recommended for normal sign-in and use. The older CLI generator still prints to standard output; do not run it through the Panel console or as a Startup Command. If the key is lost, encrypted backups cannot be restored.

If you configure S3-compatible backup storage, use a private bucket, HTTPS endpoint and a dedicated restricted credential. Configure a bucket lifecycle policy separately; local retention does not automatically delete remote objects.

## 5. Create the first administrator

**First-admin browser setup is implemented on the feature branch.** Python CI #1031 (259 tests) and container smoke #439 passed; live Panel verification is still pending. The setup steps are:

1. In Pterodactyl, stop the Orinoco server and set the hidden **First Administrator Setup Token** variable to a randomly generated value of at least 32 characters. Do not use a memorable password.
2. Start/restart Orinoco and open its web address. When the database has no accounts, the first-run setup dialog appears.
3. Enter the Panel token, choose an administrator username and create a strong password.
4. After success, return to Pterodactyl, clear the setup-token variable and restart Orinoco. The database independently prevents a second bootstrap even if the variable is accidentally left set.
5. Store the administrator password in a password manager.

The endpoint also requires the session CSRF token, compares the Panel token in constant time and throttles failed attempts. The token expires 30 minutes after each application start; restarting Orinoco re-arms the configured token. The database still prevents repeat setup after an administrator exists. It does not expose public registration. These protections passed Python CI [#1031](https://github.com/lcswolf/orinoco-ai/actions/runs/45728355190) (259 tests); container build/smoke [#439](https://github.com/lcswolf/orinoco-ai/actions/runs/45728355223) also passed. Disposable Panel verification remains a release requirement.

**Administrator recovery is implemented on the feature branch.** Python CI [#1031](https://github.com/lcswolf/orinoco-ai/actions/runs/45728355190) and container smoke [#439](https://github.com/lcswolf/orinoco-ai/actions/runs/45728355223) passed; live Panel verification is still pending. To arm it, set the hidden **Administrator Recovery Token** variable in Pterodactyl to a random value of at least 32 characters and restart Orinoco. Open the sign-in dialog and choose **Administrator locked out? Recover access**. Enter the token, the existing administrator username and a new password. The token expires 30 minutes after startup; its fingerprint is stored in the database after use, so the same token cannot be replayed after a restart. The password reset revokes every existing session. Closing the recovery dialog clears its token and password fields. After recovery, clear the Panel variable and restart Orinoco. Do not put the token or password in Startup Commands or console logs. See [Panel-first Management](PANEL_MANAGEMENT.md).

## 6. Use the web interface

### Chat and conversations

- Sign in and start a chat by entering a message.
- Orinoco sends prompts to the local model running on the same host; it does not use a hosted inference API.
- Conversations are private to your account. Use the conversation list to return to saved chats.
- A small generation queue protects the server. If the model is busy, wait and retry rather than repeatedly submitting the same prompt.

### Personal memories and preferences

- Orinoco can automatically save a limited number of useful, non-sensitive memories when memory saving is enabled.
- Review your memories and correct or delete anything that is no longer accurate.
- You can disable automatic memory saving in your user preferences.
- Memories are personal to your account and are not intended to be shared with other users.

Avoid asking the assistant to store passwords, payment details, security answers or other secrets as memories.

### Documents

- Upload supported text and office documents to your private document library: TXT, Markdown, PDF, DOCX, XLSX and PPTX.
- Each uploaded file is limited to 10 MiB.
- Orinoco extracts bounded text and uses keyword retrieval to find relevant passages.
- Private documents are only available to your account. The administrator-managed shared library is read-only for standard users.
- Remove documents you no longer need. Do not upload material you are not authorised to store on this server.

### Web research and webpage summaries

Web research is optional and requires the administrator to configure a SearXNG endpoint and enable `ENABLE_WEB_SEARCH`.

- Use the research workspace to run a search.
- In chat, use the per-message search option only when you want the assistant to research the web.
- You can provide a public webpage link for Orinoco to fetch and summarise with the local model.
- Search queries go to the configured SearXNG service and its upstream search providers. Do not treat search results or webpage text as trusted instructions.

Web search is not available when the service endpoint is blank or the feature is disabled.

## 7. Backups and recovery

Orinoco supports encrypted local backups, verification, confirmed restore and optional S3-compatible upload.

- The scheduled backup normally runs at **03:00** in the configured timezone.
- Local backups are retained for **14 days** by default.
- The backup includes application data and private documents, but not Egg/environment variables or Ollama model weights.
- Keep the encryption key and any environment-supplied session secret separately.
- A backup stored only on the VPS is not an off-site backup.
- Manual one-off backup creation and verification are run through the Pterodactyl Startup Command; Orinoco does not currently have a manual-backup button in its web interface. Follow [Updating and Rollback](UPDATING.md) and restore the normal Startup Command after each one-shot task.

Before an application update, create and verify a fresh backup. Follow [Updating and Rollback](UPDATING.md) exactly; schema rollback requires restoring the pre-update backup before starting the older image. Do not restore a backup while Orinoco is running.

## 8. Health checks

The runtime exposes two checks:

- `/healthz` — application liveness.
- `/readyz` — local-model readiness.

A live response from `/healthz` does not necessarily mean the model has finished downloading or is ready to answer. Check `/readyz` and the Pterodactyl console after first start.

## 9. Troubleshooting

| Symptom | What to check |
|---|---|
| Server stays in startup | Read the Pterodactyl console; check image pull, supervisor and Ollama messages. |
| First chat is slow | The model may still be downloading or warming up. Check `/readyz` and persistent model storage. |
| Model download fails | Check outbound DNS/HTTPS, available disk space and the console. First-run download retries transient failures before exiting visibly. |
| Chat returns busy/overloaded | A generation is already running or the queue is full. Wait for it to finish, then retry once. |
| Web search is unavailable | Confirm `ENABLE_WEB_SEARCH`, `SEARXNG_URL`, and connectivity to the configured SearXNG service. |
| HTTPS or proxy access fails | Check the domain/IP certificate, Caddy and Nginx logs, actual allocation port, firewall and proxy forwarding configuration. |
| Real client IP is always loopback | Stop and correct the proxy chain. Do not trust arbitrary forwarded headers or use a wildcard proxy allowlist. |
| Backup verification/restore fails | Confirm the correct backup key and file, read the CLI error, and do not delete recovery copies. |
| Older image will not start after update | The database may have a newer schema. Restore the verified pre-update backup before starting the older image. |

For security issues, follow [Security](../SECURITY.md). For technical details and development, see [Architecture](ARCHITECTURE.md) and [Development](DEVELOPMENT.md).

## 10. Current limitations

- The public image and live Pterodactyl install have not yet been release-verified.
- The first VPS deployment and real resource measurements remain outstanding.
- Discord and voice are planned but not available.
- S3 upload is implemented; convenient remote-download restore and remote bucket retention automation remain outstanding.
- The current initial design assumes a single web worker for process-local generation and rate limits.

Always consult [Project Status](PROJECT_STATUS.md) and the release notes for the latest verified capabilities before installing or updating.
