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

The current development branch includes Argon2 password hashing, signed session cookies, CSRF tokens for state-changing authentication requests, secure-cookie defaults, and a small in-process failed-login throttle. Session signing material is stored in the persistent data directory with restrictive file permissions when no explicit secret is configured.

These controls are a foundation, not a completed production security review. The login throttle is process-local and must be supplemented with reverse-proxy rate limits before public deployment. Session secrets and the SQLite database must remain on persistent, private storage. Never expose the data directory through the web server.

## Deployment guidance

Before exposing an Orinoco instance:

- Disable public registration and create the first administrator securely.
- Use HTTPS and strong unique credentials; enable MFA where available.
- Keep Ollama, databases and internal service ports off the public internet.
- Restrict access to approved users and keep each user's data isolated.
- Apply updates and maintain encrypted, off-server backups.
- Treat webpages, documents and other retrieved content as untrusted input.
