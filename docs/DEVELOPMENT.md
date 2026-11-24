# Development

This guide covers the first application scaffold. Orinoco is not yet a complete assistant.

## Requirements

- Python 3.12
- Git

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

Open `http://127.0.0.1:8000/healthz`. A healthy response currently confirms only that the web process is responding; it does not yet check a model, database or integrations.

## Run tests

```bash
python -m pip install pytest httpx
python -m pytest
```

## Build the container image

From the repository root:

```bash
docker build -f docker/Dockerfile -t orinoco:dev .
```

The image uses a non-root `container` account and the `/home/container` working directory expected by Pterodactyl. Pterodactyl supplies a `STARTUP` environment variable to the entrypoint. The entrypoint expands simple `{{VARIABLE}}` placeholders and executes the command without evaluating it through a shell.

For a local container test, provide a startup command explicitly:

```bash
docker run --rm -p 8000:8000 \
  -e STARTUP='uvicorn orinoco.main:app --host 0.0.0.0 --port 8000' \
  orinoco:dev
```

Then visit `http://127.0.0.1:8000/healthz`.

## Current limitations

- No login, accounts or chat interface yet.
- No database or persistent user data yet.
- No Ollama process or model downloads yet.
- No Discord, voice, search or document ingestion yet.
- No production-ready Egg manifest yet.

Do not expose this scaffold as a public assistant service.
