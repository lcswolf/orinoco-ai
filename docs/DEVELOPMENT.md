# Development

This guide covers the current custom interface, authentication, local chat, personal memory, document and optional web-search foundations. Orinoco is not yet production-ready.

## Requirements

- Python 3.12
- Git
- Optional: a local Ollama service for model responses
- Optional: a SearXNG instance for web search

## Run locally

From the repository root:

```bash
python -m venv .venv
python -m pip install -r requirements.txt
uvicorn orinoco.main:app --host 127.0.0.1 --port 8000 --reload
```

Open `http://127.0.0.1:8000/`. Sign in to use chat. The interface checks `/readyz` for the configured local Ollama model. `/healthz` checks only that the web process is responding.

Chats, memories and documents are scoped to the signed-in account. The chat API uses local Ollama on loopback and does not call an external AI inference API.

## Account bootstrap

Create the first administrator locally:

```bash
ORINOCO_DATABASE_PATH=./data/orinoco.sqlite3 python -m orinoco.admin create-admin
```

The command asks for a username and password interactively. Use a password of at least 12 characters. Administrators can create standard accounts from account settings. Public self-registration is disabled.

## Personal memories

Orinoco can extract durable, non-sensitive personal facts after a chat turn. Users can review, edit and delete their own memories. Automatic extraction uses an additional local model request and can be disabled with `AUTO_SAVE_MEMORIES=false`.

## Document libraries

Signed-in users can upload private TXT, Markdown, PDF, DOCX, XLSX and PPTX files (maximum 10 MiB each). Administrators can upload to the shared read-only library. Extracted text is stored in SQLite and indexed with FTS5. Chat retrieves bounded excerpts only from the current user's private documents and the shared library. Scanned PDFs without embedded text are not OCR-processed.

## Web research

The Research page uses a configured SearXNG instance. Set:

```bash
ENABLE_WEB_SEARCH=true
SEARXNG_URL=https://your-searxng.example
```

Search queries are sent to that SearXNG instance and any upstream search providers it uses. Do not include private information in a web search. Direct opening and summarisation of user-provided URLs is not implemented yet.

## Run tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
node --check orinoco/static/app.js
```

## Build the container image

```bash
docker build -f docker/Dockerfile -t orinoco:dev .
```

The image uses a non-root `container` account and the `/home/container` working directory expected by Pterodactyl. Pterodactyl supplies a `STARTUP` environment variable to the entrypoint, which expands simple `{{VARIABLE}}` placeholders without evaluating them through a shell.

## Current limitations

- Safe direct URL fetching and webpage summarisation.
- Search results automatically included in chat answers.
- Conversation editing/deletion, pagination and streaming.
- OCR and advanced semantic document search.
- Discord and voice integrations.
- Backup/restore tooling and production deployment.

Do not expose this development scaffold as a public assistant service.
