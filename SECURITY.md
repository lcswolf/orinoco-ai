# Security Policy

Orinoco is an early-stage project. Its security controls are still being designed and implemented; do not assume that an unreviewed build is safe for internet-facing or sensitive use.

## Reporting a vulnerability

Please do not publish details of an exploitable vulnerability in a public issue.

Until a dedicated private reporting address is published, contact the repository owner through GitHub's private vulnerability reporting feature if it is enabled for this repository. Include:

- A clear description and potential impact.
- The affected version, commit or deployment configuration.
- Reproduction steps or a proof of concept, where safe.
- Any suggested mitigation.

Please allow time for the report to be reviewed before publicly disclosing it.

## Sensitive information

Never commit or attach passwords, Discord bot tokens, private keys, session cookies, .env files, personal conversations, user memories, uploaded documents, databases or backups.

If a secret is accidentally committed, revoke or rotate it immediately. Removing it from the latest commit does not make an exposed secret safe again.

## Current authentication foundation

The current development branch includes Argon2 password hashing, signed session cookies, CSRF tokens for state-changing authentication requests, secure-cookie defaults, conservative content-security and browser security headers, and a bounded in-process failed-login throttle. Session signing material is stored in the persistent data directory with restrictive file permissions when no explicit secret is configured.

These controls are a foundation, not a completed production security review. The login throttle is process-local and must be supplemented with reverse-proxy rate limits before public deployment. Session secrets and the SQLite database must remain on persistent, private storage. Never expose the data directory through the web server.

## Document uploads and retrieval

The current document library accepts TXT, Markdown, PDF, DOCX, XLSX and PPTX files up to 10 MiB each. Before public deployment, configure the HTTPS reverse proxy to reject request bodies above approximately 11 MiB on the upload endpoints; the application validates the file size after multipart parsing. The optional webpage summariser only fetches public HTTP/HTTPS destinations on standard ports, resolves and pins hostnames to public IP addresses, revalidates redirects and limits response size. Extracted text is stored in the application database and original uploads are stored under the private data directory. The web server must never serve that directory directly.

Uploaded documents are untrusted content. Their text may be included as reference excerpts in the owner's chat or in the shared-library context; it must not be treated as instructions. Passwords, secrets, precise personal information and sensitive facts should not be added to shared documents. Office ZIP containers are checked for encrypted entries, excessive entry counts and more than 25 MiB of uncompressed content before parsing. The current extraction pipeline is bounded but is not a malware scanner or a full document-sandboxing system.

## Deployment guidance

Before exposing an Orinoco instance:

- Disable public registration and create the first administrator securely.
- Use HTTPS and strong unique credentials. Orinoco does not yet provide app-level MFA; enable MFA on GitHub, hosting-provider and Pterodactyl accounts where available.
- Keep Ollama bound to loopback, databases and internal service ports off the public internet. Production inference is fixed to the local Ollama service and ignores HTTP proxy environment variables.
- Restrict access to approved users and keep each user's data isolated.
- Apply updates and maintain encrypted, off-server backups.
- Treat webpages, documents and other retrieved content as untrusted input.
