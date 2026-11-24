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

## Deployment guidance

Before exposing an Orinoco instance:

- Disable public registration and create the first administrator securely.
- Use HTTPS and strong unique credentials; enable MFA where available.
- Keep Ollama, databases and internal service ports off the public internet.
- Restrict access to approved users and keep each user's data isolated.
- Apply updates and maintain encrypted, off-server backups.
- Treat webpages, documents and other retrieved content as untrusted input.
