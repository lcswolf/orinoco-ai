# Panel-first operations and management requirements

**Status: partially implemented in `feature/panel-first-bootstrap`; CI and live Panel verification are still outstanding.**

Orinoco's operational requirement is that, after the VPS has been provisioned with Pterodactyl Panel and Wings and the Orinoco Egg has been imported, routine Orinoco administration must not require SSH, Docker commands or a shell on the host.

Pterodactyl is the control plane for the Orinoco server. The Orinoco web interface is the control plane for application accounts and user data. The host remains an infrastructure layer; its initial provisioning and any host-wide networking services are separate from day-to-day Orinoco operation.

## Management boundary

| Task | Intended place | Current position |
|---|---|---|
| Start, stop, restart and observe Orinoco | Pterodactyl Console | Designed; live Panel test outstanding |
| Change model, context, memory and backup settings | Pterodactyl server variables | Egg variables exist; live Panel test outstanding |
| View runtime and scheduler logs | Pterodactyl Console | Designed; live Panel test outstanding |
| Upload/download application files and backup archives | Pterodactyl File Manager | Depends on Panel file-manager permissions and live test |
| First administrator setup | Orinoco first-run web setup, initiated/configured through Panel | **Web bootstrap API and setup dialog implemented on feature branch; token-gated, rate-limited and database-enforced one-time creation; CI/live verification pending** |
| Administrator account recovery | Secure Panel-triggered recovery workflow or authenticated admin UI | **Not implemented as a Panel-only recovery path; current CLI requires SSH and a TTY** |
| Create/suspend ordinary accounts and edit assistant persona | Orinoco admin web interface | Implemented in application; UI/live verification outstanding |
| Generate backup encryption key | Browser-side secure generator or another documented Panel-only safe workflow | **Current CLI prints to stdout; do not expose key in persistent console logs** |
| Create and verify backups | Orinoco admin UI or a Panel-triggered one-shot maintenance command | Scheduled backups implemented; manual maintenance currently uses Startup Command |
| Restore backup | Panel-triggered maintenance mode / one-shot command while app is stopped | CLI exists; runbook uses Panel Startup Command; live recovery drill outstanding |
| Apply application update and migration | Panel image selection plus Panel-triggered migration command | Runbook exists; automated image switching and live rollback drill outstanding |
| Configure host firewall, DNS, Caddy/Nginx and Tailscale | Initial infrastructure provisioning / host administration | Host-level SSH steps currently documented; not Orinoco Egg controls |
| Update Pterodactyl Panel, Wings and host OS | Infrastructure administrator / hosting workflow | Outside Orinoco's application Egg |

## Rules for Panel-first operation

1. Never ask an Orinoco owner to discover a Docker container ID or run Docker exec for normal setup, account management, backup, restore or updates.
2. Never ask the owner to paste a password, backup key or recovery token into a Startup Command, command argument, public log or Git commit.
3. Use hidden, administrator-only Egg variables for configuration secrets. Explain that hidden Panel variables are still readable by processes inside the container and are not a general-purpose secret vault.
4. Prefer authenticated web workflows for routine account management. First-run bootstrap and lockout recovery must use single-use, time-limited credentials and must be disabled after success.
5. For maintenance operations that must run with the web app stopped, use a clearly documented one-shot Startup Command controlled in the Panel. It must emit non-secret progress and a clear success/failure result, then return the operator to the normal startup command.
6. Do not claim a Panel workflow is complete until it has been exercised on a disposable Panel 1.13.0 server, including failure and recovery cases.
7. Keep host-level networking distinct. SSH may be needed once to provision Ubuntu, Panel/Wings and host ingress. If the requirement is literally zero SSH even for host provisioning, the VPS must be supplied with a prebuilt/managed Pterodactyl node and managed ingress; the Orinoco Egg cannot install or safely administer host services from inside its isolated container.

## Required implementation work

- [x] Replace SSH/TTY-only first-admin creation with a browser setup flow enabled by a hidden Panel variable. The feature branch uses constant-time token comparison, CSRF protection, per-client attempt throttling and an atomic database guard that refuses setup once any account exists. The token remains in the process environment until removed from the Panel, but cannot create a second account after the first succeeds. CI and live Panel testing are still pending.
- Provide a safe administrator recovery path that can be armed from the Panel, is single-use, revokes existing sessions, and cannot be used as a public password-reset endpoint.
- Provide a safe backup-key creation workflow that does not leave the key in persistent console logs. Explain how to copy it once into the hidden Egg variable and store an off-server copy.
- Review the existing Panel Startup Command procedures for backup, verify, migration and restore. Make the maintenance mode obvious, validate paths, avoid secret output, and make normal startup restoration explicit.
- Add a Panel-first acceptance checklist to the disposable-server test plan: setup, recovery, settings changes, console logs, backup creation/verification, restore, update, rollback and file access.
- Review Caddy/Nginx/Tailscale separately. Decide whether to keep them as one-time host setup or package a supported ingress service. Do not imply that Pterodactyl's ordinary server console can administer host services.

## Release acceptance

The Panel-first requirement is met only when a fresh disposable Panel server can be installed, configured, bootstrapped, operated, backed up, restored and updated without SSH or Docker commands after the infrastructure prerequisites are ready. Any remaining host-only task must be explicitly identified as infrastructure administration, not routine Orinoco management.
