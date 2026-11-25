# Orinoco AI User and Setup Guide

**Status: preview guide.** Orinoco's application and container are under active development. The Docker image has not been published and the Pterodactyl Egg has not yet been imported and tested on a live Panel. Use this guide for planning and for a future test installation only; do not treat the steps as a production-ready deployment until the release gate in [Project Status](PROJECT_STATUS.md) is cleared.

This guide is intended to cover the complete user journey: preparing a host, installing and configuring Orinoco, creating the first administrator, using the web interface, managing data and backups, and troubleshooting.

## 1. What you need

For the planned first installation:

- A Linux VPS with a public IPv4 address. The current sizing plan is 4 vCPU, 6 GB RAM and 100 GB NVMe; this is a target to test, not a validated minimum.
- Ubuntu 24.04 LTS on the host.
- Pterodactyl Panel 1.13.0 (stable 1.x) and a working Wings node.
- A Pterodactyl allocation for Orinoco's web interface.
- A domain name if you want the public HTTPS subdomain.
- SSH access with permission to configure the host.
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

Generate a key using the Orinoco backup utility:

```sh
python -m orinoco.backups generate-key
```

Use the key-generation command in the Orinoco runtime or a trusted environment with the same application package. Copy the generated key into the hidden `ORINOCO_BACKUP_KEY` Egg variable and store a separate copy in a password manager or other secure location **not on the VPS**. If you lose this key, encrypted backups cannot be restored. Do not put it in Git, screenshots, tickets or ordinary notes.

If you configure S3-compatible backup storage, use a private bucket, HTTPS endpoint and a dedicated restricted credential. Configure a bucket lifecycle policy separately; local retention does not automatically delete remote objects.

## 5. Create the first administrator

The first administrator must be created using an interactive terminal. The Pterodactyl console is attached to the process supervisor and is not a suitable password prompt.

1. In the host's SSH session, identify the Orinoco container:
   ```sh
   docker ps
   ```
2. Open the interactive admin-creation command, replacing `CONTAINER_ID` with the actual container ID:
   ```sh
   docker exec -it CONTAINER_ID python -m orinoco.admin create-admin
   ```
3. Follow the prompts to enter the administrator username and password. Use a unique, strong password.
4. Open your configured Orinoco HTTPS address and sign in.

To reset a user's password from an interactive host terminal, use:

```sh
docker exec -it CONTAINER_ID python -m orinoco.admin reset-password USERNAME
```

Do not put passwords into a Pterodactyl startup command or a non-interactive console. These commands are documented for the planned runtime; validate them against the released image before relying on them.

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
