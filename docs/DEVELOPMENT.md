# Development

This guide covers the current custom interface and local runtime foundations. Orinoco is not yet a complete assistant.

## Requirements

- Python 3.12
- Git
- Optional: Ollama installed locally if you want the interface readiness indicator to show a loaded model

## Run locally

From the repository root:

```bash
python -m venv .venv
```

Activate the environment, then install dependencies:

```bash
python -m pip install -r requirements.txt
```

Start the development server:

```bash
uvicorn orinoco.main:app --host 127.0.0.1 --port 8000 --reload
```

Open `http://127.0.0.1:8000/` to view the custom Orinoco interface. The interface checks `/readyz` and displays whether the configured local Ollama model is available. `/healthz` checks only that the web process is responding.

The current web composer is intentionally inactive. Do not expose an unauthenticated chat endpoint; authentication and per-user storage must be completed first.

## Account foundation

The repository now includes SQLite account storage and Argon2 password hashing primitives. A local-only bootstrap command can create an administrator account:

```bash
ORINOCO_DATABASE_PATH=./data/orinoco.sqlite3 python -m orinoco.admin create-admin
```

The command asks for a username and password interactively; it does not place the password in shell history. Use a password of at least 12 characters. The web interface includes a sign-in dialog backed by signed sessions and CSRF-protected login/logout routes. Account creation is still deliberately local-only; public registration, user-management screens, account recovery and MFA are not implemented yet.

## Run tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```

## Build the container image

From the repository root:

```bash
docker build -f docker/Dockerfile -t orinoco:dev .
```

The image uses a non-root `container` account and the `/home/container` working directory expected by Pterodactyl. Pterodactyl supplies a `STARTUP` environment variable to the entrypoint. The entrypoint expands simple `{{VARIABLE}}` placeholders and executes the command without evaluating it through a shell.

The intended container startup command is:

```bash
supervisord -n -c /opt/orinoco/docker/supervisord.conf
```

For a local container test, the image's normal supervisor startup can be used with the model download disabled:

```bash
docker run --rm -p 8000:8000 \
  -e STARTUP='supervisord -n -c /opt/orinoco/docker/supervisord.conf' \
  -e SERVER_PORT=8000 \
  -e AUTO_DOWNLOAD_MODEL=false \
  orinoco:dev
```

Then visit `http://127.0.0.1:8000/`.

## Current limitations

- No user-management, account recovery or MFA screens.
- No authenticated chat endpoint or conversation history.
- No memory, document ingestion, web search or URL summarisation.
- No Discord or voice integration.
- The Pterodactyl Egg and container image are still preview/development artefacts and have not been deployed to the user's Panel.

Do not expose this development scaffold as a public assistant service.
