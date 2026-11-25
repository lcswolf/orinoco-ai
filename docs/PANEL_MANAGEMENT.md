# Panel-first operations and management requirements

**Status: partially implemented in `feature/panel-first-bootstrap`; Python CI #1022 passed (259 tests) and container build/smoke #429 passed. Live Panel 1.13.0 and real-browser verification remain outstanding.**

Orinoco's operational requirement is that, after the VPS has been provisioned with Pterodactyl Panel and Wings and the Orinoco Egg has been imported, routine Orinoco administration must not require SSH, Docker commands or a shell on the host.

Pterodactyl is the control plane for the Orinoco server. The Orinoco web interface is the control plane for application accounts and user data. The host remains an infrastructure layer; its initial provisioning and any host-wide networking services are separate from day-to-day Orinoco operation.

## Management boundary

| Task | Intended place | Current position |
|---|---|---|
| Start, stop, restart and observe Orinoco | Pterodactyl Console | Designed; live Panel test outstanding |
| Change model, context, memory and backup settings | Pterodactyl server variables | Egg variables exist; live Panel test outstanding |
| View runtime and scheduler logs | Pterodactyl Console | Designed; live Panel test outstanding |
| Upload/download application files and backup archives | Pterodactyl File Manager | Depends on Panel file-manager permissions and live test |
| First administrator setup | Orinoco first-run web setup, initiated/configured through Panel | **Web bootstrap API and setup dialog implemented on feature branch; token-gated, rate-limited and database-enforced one-time creation; Python CI #1022 (259 tests) and container smoke #429 passed; live Panel verification pending** |
| Administrator account recovery | Secure Panel-triggered recovery workflow or authenticated admin UI | **One-time, 30-minute Panel token recovery API and browser dialog implemented on feature branch; Python CI #1022 (259 tests) and container smoke #429 passed; live Panel verification pending** |
| Create/suspend ordinary accounts and edit assistant persona | Orinoco admin web interface | Implemented in application; UI/live verification outstanding |
| Generate backup encryption key | Orinoco administrator Settings (browser-only generator) | **Browser generator implemented on feature branch; supports direct IP-and-port access with manual copy fallback; Python CI #1022 (259 tests) and container smoke #429 passed; manual browser verification pending** |
| Create and verify backups | Built-in scheduler (automatic) or Pterodactyl Startup Command (manual) | Daily encrypted scheduler is implemented; manual prepare/verify/upload uses one-shot CLI commands from the Panel. There is no manual-backup button in the Orinoco web UI. |
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

- [x] Replace SSH/TTY-only first-admin creation with a browser setup flow enabled by a hidden Panel variable. The feature branch uses constant-time token comparison, CSRF protection, per-client attempt throttling, a 30-minute validity window after application start and an atomic database guard that refuses setup once any account exists. The token remains in the process environment until removed from the Panel, but cannot create a second account after the first succeeds. Python CI [#1022](https://github.com/lcswolf/orinoco-ai/actions/runs/45707665093) passed (259 tests), and container build/smoke [#429](https://github.com/lcswolf/orinoco-ai/actions/runs/45707665035) passed; live Panel testing is still pending.
- [x] Add Panel-triggered administrator recovery on the feature branch: a 30-minute token window, constant-time token comparison, CSRF and throttling, a durable database record of consumed token fingerprints, and password/session-version update in one transaction. The browser flow only targets an existing active administrator. Python CI [#1022](https://github.com/lcswolf/orinoco-ai/actions/runs/45707665093) and container build/smoke [#429](https://github.com/lcswolf/orinoco-ai/actions/runs/45707665035) passed; live Panel testing is pending.
- [x] Add a browser-only backup-key generator on the feature branch using `crypto.getRandomValues`. It generates the same 32-byte URL-safe base64 format as the backup CLI and never sends or stores the key on the server. The owner must copy it to the hidden Egg variable and an independent off-server password manager. Real-browser verification remains required. Temporary recovery credentials and generated backup-key values are cleared from their dialogs when closed.
- [x] Review the Panel Startup Command procedures for backup, verify, migration and restore. The runbook makes one-shot maintenance mode and normal startup restoration explicit; restore requires `--confirm`, backup sources must be regular `.oribak` files (not symlinks), and the CLI reads secrets from environment variables rather than command arguments. The backup-key CLI still prints the key and is explicitly prohibited in the Panel console; use the browser generator instead.
- [x] Add a Panel-first acceptance checklist to the disposable-server test plan covering setup, recovery, settings changes, console logs, backup creation/verification, restore, update, rollback and file access.
- Review Caddy/Nginx/Tailscale separately. Decide whether to keep them as one-time host setup or package a supported ingress service. Do not imply that Pterodactyl's ordinary server console can administer host services.

## Release acceptance

The Panel-first requirement is met only when a fresh disposable Panel server can be installed, configured, bootstrapped, operated, backed up, restored and updated without SSH or Docker commands after the infrastructure prerequisites are ready. Any remaining host-only task must be explicitly identified as infrastructure administration, not routine Orinoco management.
