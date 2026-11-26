# Standalone Docker Compose installation

**Status: staging instructions.** Orinoco is already packaged as a Docker image, and the same image is intended to run under either Pterodactyl or ordinary Docker Compose. This guide documents the standalone path; it is not evidence that a live standalone deployment has been tested or that Orinoco is production-ready. Check [Project Status](PROJECT_STATUS.md) and the current release notes before installing.

Pterodactyl is an optional management layer. It supplies a web UI for server lifecycle, allocations, resource limits, console logs and scheduled backups. Docker is still the container runtime underneath it. A standalone Compose installation uses Docker directly and does not need Pterodactyl or Wings.

## 1. What runs

The Orinoco image is an all-in-one container:

- Orinoco web application.
- Ollama local inference service.
- First-run model initialisation.
- Backup scheduler (disabled by default in images containing the optional-backup change).

You do **not** need a separate Ollama container. Ollama listens on container loopback only and must not be published to the host or internet.

The persistent application data directory is `/home/container/data` inside the container. It holds the SQLite database, model files, uploaded documents, session data and backup files. Mount this directory to a persistent host directory.

## 2. Prerequisites

- A Linux host with Docker Engine and the Docker Compose plugin installed using Docker's official instructions.
- A supported image for the host architecture. The currently published staging image is linux/amd64; check release notes before using another architecture.
- Enough RAM and disk for the chosen local model, its download/cache, application data and the operating system. The project has not yet established a validated production minimum. Start with a small curated model and measure actual resource use.
- A network path for the web interface. For a public deployment, use a properly configured HTTPS reverse proxy and firewall; do not expose the raw application port directly to the internet.

Docker installation and host firewall administration are host-level tasks. They are not performed by Orinoco itself.

## 3. Create the Compose project

Create a directory for the installation and enter it:

```sh
mkdir -p ~/orinoco
cd ~/orinoco
mkdir -p data
```

Create a `.env` file from the example below. Set `ORINOCO_IMAGE` to the exact immutable image tag published for the release you intend to run. Do not guess a tag or rely on the mutable `:stable` tag for a production deployment.

```dotenv
# Replace this with the exact immutable image tag from the release notes.
ORINOCO_IMAGE=ghcr.io/lcswolf/orinoco-ai:REPLACE_WITH_RELEASE_TAG

# Host port. The example Compose file binds it to loopback only.
ORINOCO_PORT=8000

# Generate a unique random token for first-administrator setup.
ORINOCO_BOOTSTRAP_TOKEN=REPLACE_WITH_AT_LEAST_32_RANDOM_CHARACTERS

TIMEZONE=Europe/London
AI_MODEL=qwen2.5:0.5b
AUTO_DOWNLOAD_MODEL=false
MODEL_CONTEXT=1024
AUTO_SAVE_MEMORIES=false
ENABLE_WEB_SEARCH=false

# Keep the Orinoco-managed scheduler disabled if you use another backup system.
ORINOCO_BACKUP_ENABLED=false
```

Generate a bootstrap token rather than choosing a memorable value:

```sh
openssl rand -hex 32
```

Paste the output into `ORINOCO_BOOTSTRAP_TOKEN`, then protect the file:

```sh
chmod 600 .env
```

Do not commit `.env`, share it, or paste its contents into support requests. It contains a credential that processes inside the container can read.

## 4. Compose file

Create `compose.yaml`:

```yaml
services:
  orinoco:
    image: ${ORINOCO_IMAGE:?Set ORINOCO_IMAGE in .env to an immutable release tag}
    container_name: orinoco
    restart: unless-stopped
    init: true
    ports:
      # Localhost only. Put a trusted HTTPS reverse proxy in front for remote access.
      - "127.0.0.1:${ORINOCO_PORT:-8000}:8000"
    volumes:
      - ./data:/home/container/data
    environment:
      # The image entrypoint expands this command before starting Supervisor.
      STARTUP: "supervisord -n -c /opt/orinoco/docker/supervisord.conf"
      SERVER_PORT: "8000"
      TIMEZONE: ${TIMEZONE:-Europe/London}
      TZ: ${TIMEZONE:-Europe/London}

      # Local Ollama is included in this same container.
      OLLAMA_MODELS: /home/container/data/models
      OLLAMA_NO_CLOUD: "1"

      AI_MODEL: ${AI_MODEL:-qwen2.5:0.5b}
      AUTO_DOWNLOAD_MODEL: ${AUTO_DOWNLOAD_MODEL:-false}
      MODEL_CONTEXT: ${MODEL_CONTEXT:-1024}
      AI_CONCURRENCY: "1"
      AUTO_SAVE_MEMORIES: ${AUTO_SAVE_MEMORIES:-false}
      ENABLE_WEB_SEARCH: ${ENABLE_WEB_SEARCH:-false}
      SEARXNG_URL: ${SEARXNG_URL:-}

      ORINOCO_DATABASE_PATH: /home/container/data/orinoco.sqlite3
      ORINOCO_BOOTSTRAP_TOKEN: ${ORINOCO_BOOTSTRAP_TOKEN:-}
      ORINOCO_BACKUP_ENABLED: ${ORINOCO_BACKUP_ENABLED:-false}
      ORINOCO_BACKUP_KEY: ${ORINOCO_BACKUP_KEY:-}
```

The Compose file deliberately publishes only the Orinoco web port, and only on host loopback. It does not publish Ollama's port 11434. Do not add an Ollama port mapping.

## 5. Prepare persistent directory permissions

The application runs as an unprivileged user inside the image. Before the first start, ask the image which numeric user it uses, then give that user ownership of the host data directory:

```sh
ORINOCO_UID=$(docker compose run --rm --no-deps --entrypoint id orinoco -u)
ORINOCO_GID=$(docker compose run --rm --no-deps --entrypoint id orinoco -g)
sudo chown -R "$ORINOCO_UID:$ORINOCO_GID" ./data
```

Run these commands from the directory containing your `.env` file. If your Docker installation requires `sudo` for Docker commands, use it consistently. Do not solve permission problems by making the data directory world-writable.

## 6. Start Orinoco

Check the Compose configuration, pull the selected image and start the service:

```sh
docker compose config
docker compose pull
docker compose up -d
docker compose logs -f --tail=200 orinoco
```

On first start, watch the logs for Ollama and the web application startup messages. With `AUTO_DOWNLOAD_MODEL=false`, model download is intentionally skipped and `/readyz` will report that a model is not ready. This is expected for an application-only first boot.

Check the endpoints from the Docker host (replace `8000` if you changed `ORINOCO_PORT` in `.env`):

```sh
curl -i http://127.0.0.1:8000/healthz
curl -i http://127.0.0.1:8000/readyz
```

A healthy `/healthz` confirms application liveness; it does not mean the model is ready. `/readyz` should become ready after the selected model is installed.

## 7. Create the first administrator

1. Open Orinoco through the local reverse proxy or an approved private access path.
2. Complete the first-run administrator setup using the bootstrap token from `.env`.
3. After the administrator account has been created, remove the token value from `.env` (leave it blank) and restart the service:

```sh
docker compose up -d
```

The database prevents a second first-administrator bootstrap. Do not leave the bootstrap token configured after setup.

## 8. Download and select a model

Once the app-only startup and first-admin setup have been checked:

1. Edit `.env` and set `AUTO_DOWNLOAD_MODEL=true`.
2. Keep `AI_MODEL` on a model supported by the current image and appropriate for the host's available memory.
3. Start/recreate the service:

```sh
docker compose up -d
docker compose logs -f --tail=200 orinoco
```

The initial download may take time and disk space. Check `/readyz` after the download. Do not assume that a model that fits on one VPS will fit on another. The initial runtime uses one simultaneous generation; hardware-aware automatic tuning is a planned improvement, not yet a completed feature.

## 9. Day-to-day commands

Run these from the directory containing `compose.yaml`:

| Task | Command |
| --- | --- |
| View status | `docker compose ps` |
| Follow logs | `docker compose logs -f --tail=200 orinoco` |
| Restart | `docker compose restart orinoco` |
| Stop | `docker compose stop orinoco` |
| Start | `docker compose start orinoco` |
| View resource use | `docker stats orinoco` |
| Pull configured image and recreate | `docker compose pull && docker compose up -d` |

The same application settings and modules are used regardless of whether Orinoco is managed by Compose or Pterodactyl. Pterodactyl-specific controls such as allocations, Egg variables and Panel scheduled backups are not present in standalone Compose; configure equivalent host-level services where required.

## 10. Backups and updates

The host directory `./data` is the persistent Orinoco data volume. Protect it with restricted filesystem permissions and include it in a secure backup plan. Keep backup encryption keys and other secrets separately, away from the host.

For a simple filesystem-level backup, stop Orinoco first so SQLite and other application files are not changing while copied:

```sh
docker compose stop orinoco
tar --numeric-owner -czf "orinoco-data-$(date +%Y%m%d-%H%M%S).tar.gz" data
docker compose start orinoco
```

Move the archive off the VPS and protect it appropriately; it contains private user data and may include local model files. Test recovery before relying on a backup. Orinoco's own encrypted backup/verification/restore tools are separate from this host-level example. Its automatic backup scheduler is optional and disabled by default in the release containing that feature.

Before an application update, create and verify a backup. Change `ORINOCO_IMAGE` to the exact immutable tag for the new release, then run:

```sh
docker compose pull
docker compose up -d
docker compose logs -f --tail=200 orinoco
```

Do not remove the data directory when replacing an image. If an update fails, follow the release's rollback instructions; a database schema migration may mean that simply switching to an older image is unsafe without restoring the pre-update backup.

## 11. Remote access and security

The example binds the web port to `127.0.0.1` intentionally. For remote use, put a trusted reverse proxy with HTTPS in front of it, or use a private network such as Tailscale. Configure the proxy and Orinoco's trusted-proxy settings according to [Network Deployment](NETWORK_DEPLOYMENT.md).

- Do not expose the raw Orinoco application port directly to the public internet.
- Do not expose Ollama port 11434.
- Do not expose the SQLite database or the `data` directory.
- Keep `.env` and backup encryption keys private.
- Do not run the container as privileged or mount the Docker socket into it.
- Keep Docker Engine, the host OS and the reverse proxy updated.
- Use a firewall and test access from outside the host.

## 12. Troubleshooting

| Symptom | What to check |
| --- | --- |
| Container exits immediately | Check that `STARTUP` is present in the Compose environment and inspect `docker compose logs orinoco`. |
| Data directory is not writable | Re-check the numeric UID/GID from the image and ownership of `./data`. |
| `/healthz` is unavailable | Check `docker compose ps`, container logs and host port conflicts. |
| `/readyz` reports model missing | Check `AUTO_DOWNLOAD_MODEL`, `AI_MODEL`, disk space and Ollama startup logs. |
| Model download fails | Check outbound DNS/HTTPS, free disk space and logs; retry only after resolving the cause. |
| Web search is unavailable | It is disabled in the example. Enable it only after configuring a reachable SearXNG service and `SEARXNG_URL`. |
| Remote access fails | Check the reverse proxy, TLS certificate, firewall and that the proxy can reach the loopback-published host port. |

## Current limitations

- Standalone Docker Compose has not yet been validated in a live staging environment.
- The published image's anonymous GHCR pull access remains a separate release check.
- The current published image may lag behind the latest merged source changes. Use only the exact image tag named in the current release notes; a merged pull request does not automatically publish a new image.
- Live Pterodactyl import/deployment and standalone Compose deployment are separate acceptance tests.
- Current published image architecture and model support are release-specific; consult the release notes before choosing a host or model.
