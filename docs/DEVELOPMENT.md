# Development

This guide covers the custom interface, authentication, local chat, per-user response preferences, administrator-managed core persona, personal memory, document handling and optional web research. Orinoco is not yet production-ready.

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
ORINOCO_COOKIE_SECURE=false uvicorn orinoco.main:app --host 127.0.0.1 --port 8000 --reload
```

On Windows PowerShell, set the development-only cookie override in the current
terminal before starting the server:

```powershell
$env:ORINOCO_COOKIE_SECURE = "false"
python -m uvicorn orinoco.main:app --host 127.0.0.1 --port 8000 --reload
```

Open `http://127.0.0.1:8000/`. Sign in to use chat. The cookie override is for local HTTP development only; keep the secure-cookie default enabled behind HTTPS in production. The interface checks `/readyz` for the configured local Ollama model. `/healthz` checks only that the web process is responding.

Chats, memories and documents are scoped to the signed-in account. The chat API uses local Ollama on loopback and does not call an external AI inference API.

## Account bootstrap

Create the first administrator locally:

```bash
ORINOCO_DATABASE_PATH=./data/orinoco.sqlite3 python -m orinoco.admin create-admin
```

The command asks for a username and password interactively. Use a password of at least 12 characters. Administrators can create standard accounts from account settings. Public self-registration is disabled.

## Personal memories

Orinoco can extract durable, non-sensitive personal facts after a chat turn. Users can review, edit and delete their own memories. Automatic extraction uses an additional local model request and can be disabled with `AUTO_SAVE_MEMORIES=false`. Per-user response preferences (bright/calm/professional voice, friendly/direct/playful tone and concise/balanced/detailed answers) are stored in SQLite and applied only to that account's chat prompt. Administrators can edit the shared core persona and humour level; safety and privacy guardrails are appended after custom style guidance.

## Document libraries

Signed-in users can upload private TXT, Markdown, PDF, DOCX, XLSX and PPTX files (maximum 10 MiB each). Administrators can upload to the shared read-only library. Extracted text is stored in SQLite and indexed with FTS5. Chat retrieves bounded excerpts only from the current user's private documents and the shared library. Scanned PDFs without embedded text are not OCR-processed.

## Web research

The Research page uses a configured SearXNG instance. Set:

```bash
ENABLE_WEB_SEARCH=true
SEARXNG_URL=https://your-searxng.example
```

Search queries are sent to that SearXNG instance and any upstream search providers it uses. Do not include private information in a web search. Users can also paste a public URL into the Research page for local summarisation. The fetcher pins DNS resolutions to public IP addresses, blocks private/local networks and non-standard ports, validates redirects, and limits downloaded content. Only public HTTP/HTTPS pages are supported.

## Encrypted backups and recovery

The backup CLI creates an AES-256-GCM encrypted `.oribak` file. It includes a
SQLite online-backup snapshot (including committed WAL data), uploaded documents,
the persistent session-signing file when it is file-based, and a manifest with
the selected model name. Large Ollama model weights are excluded so routine
backups remain practical; they can be downloaded again.

Generate the encryption key once:

```bash
python -m orinoco.backups generate-key
```

Store that key in a password manager or other secure location **outside the
VPS**. Set it as `ORINOCO_BACKUP_KEY` for each backup, verification and restore
operation. Losing this key makes encrypted backups unrecoverable. Never put
the key in GitHub, a public Egg file or the same backup destination.

Create and verify a backup:

```bash
python -m orinoco.backups create
python -m orinoco.backups verify /home/container/data/backups/orinoco-YYYYMMDDTHHMMSSZ.oribak
```

Configure an S3-compatible private bucket using the hidden Egg variables
`ORINOCO_BACKUP_S3_ENDPOINT`, `ORINOCO_BACKUP_S3_BUCKET`,
`ORINOCO_BACKUP_S3_ACCESS_KEY_ID`, `ORINOCO_BACKUP_S3_SECRET_ACCESS_KEY`,
and (optionally) `ORINOCO_BACKUP_S3_REGION` and
`ORINOCO_BACKUP_S3_PREFIX`. The endpoint must use HTTPS. Use a dedicated
restricted credential that can write and inspect objects only in this backup
bucket. Do not enable public bucket access.

After creating and verifying a local backup, upload it:

```bash
python -m orinoco.backups upload /home/container/data/backups/orinoco-YYYYMMDDTHHMMSSZ.oribak
```

The command uploads only encrypted `.oribak` files, sends no public ACL,
records a SHA-256 checksum as object metadata, checks the remote object size,
then downloads and hashes the stored bytes before reporting success.

The container now runs a supervised daily backup scheduler. It defaults to
03:00 in `TIMEZONE` (Europe/London by default), with 14 days of local backup
retention. Configure `ORINOCO_BACKUP_TIME` in 24-hour `HH:MM` format and
`ORINOCO_BACKUP_RETENTION_DAYS` between 1 and 365 in the Egg. The scheduler
creates a local encrypted backup, optionally uploads and verifies it when an
S3 endpoint is configured, and only then prunes expired local backups. If an
off-site upload fails, it keeps the new local backup and does not prune older
ones. Failures are written to the Pterodactyl console and recorded in
`/home/container/data/backups/.scheduler-status.json`; this file contains
operational status only, not credentials. The scheduler runs once per local
calendar day and catches up once after a restart if that day's scheduled time
has already passed. Configure an object-storage lifecycle policy separately
if remote retention is required. Keep the encryption key and object-storage
credentials separate from the backup bucket.

For recovery, stop Orinoco first, preserve the current server data, then run:

```bash
python -m orinoco.backups verify /path/to/backup.oribak
python -m orinoco.backups restore /path/to/backup.oribak --confirm
```

Restore refuses to run without `--confirm`, validates the encrypted archive
and SQLite database before replacing data, and leaves `.pre-restore` recovery copies of the database, document directory
and file-based session secret when those items existed before restore. Keep the process stopped throughout restore.
If `ORINOCO_SECRET_KEY` is supplied through the environment, preserve that
secret separately; the backup cannot read it back from the process environment.
After restore, check `/healthz`, `/readyz`, sign-in, conversations and documents.

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

- Conversation editing/deletion, pagination and streaming.
- OCR and advanced semantic document search.
- Discord and voice integrations.
- Remote object-storage retention/lifecycle policy and restore-from-remote convenience; safe application updates and rollback; production deployment.

Do not expose this development scaffold as a public assistant service.
