# Development

This guide covers the current custom interface, authentication, local chat and memory foundations. Orinoco is not yet a complete assistant.

## Requirements

- Python 3.12
- Git
- Optional: Ollama installed locally if you want to use the interface with a local model

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

Open `http://127.0.0.1:8000/` to view the custom Orinoco interface. Sign in to use chat. The interface checks `/readyz` and displays whether the configured local Ollama model is available. `/healthz` checks only that the web process is responding.

Chats are stored in SQLite and scoped to the signed-in account. The chat API uses the local Ollama service on loopback; it does not call an external AI inference API.

## Account bootstrap

The repository includes SQLite account storage and Argon2 password hashing. A local-only command creates the first administrator:

```bash
ORINOCO_DATABASE_PATH=./data/orinoco.sqlite3 python -m orinoco.admin create-admin
```

The command asks for a username and password interactively; it does not place the password in shell history. Use a password of at least 12 characters. Administrators can create standard accounts from the account settings panel. Public self-registration is disabled.

## Personal memories

Orinoco can extract a small number of durable, non-sensitive personal facts after a chat turn. These are stored against the signed-in account, included only in that account's future chat context, and can be reviewed, edited or deleted from **My memories** in settings.

Automatic memory extraction uses an additional local model request and can be disabled with:

```bash
AUTO_SAVE_MEMORIES=false
```

The extractor is deliberately conservative and filters common secret/contact/address patterns and selected sensitive categories. It is not infallible; users should review saved memories.

## Document libraries

Signed-in users can upload private TXT, Markdown, PDF, DOCX, XLSX and PPTX files (maximum 10 MiB per file). Administrators can upload documents to the shared library, which standard users can read but cannot modify. Text is extracted locally and indexed in SQLite FTS5; relevant excerpts from only the current user's private files and the shared library may be added to that user's chat prompt as untrusted reference material.

Scanned PDFs without extractable text are not OCR-processed. Uploaded files and extracted text are stored in the private data directory/database and must be included in encrypted off-server backups. They are not used to train a model.

## Run tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
node --check orinoco/static/app.js
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

## Current limitations

- No conversation deletion/editing, pagination or streaming responses.
- No OCR for scanned PDFs, advanced semantic/vector search or document pagination.
- No web search or URL summarisation.
- No Discord or voice integration.
- The Pterodactyl Egg and container image are preview/development artefacts and have not been deployed to the user's Panel.

Do not expose this development scaffold as a public assistant service.
