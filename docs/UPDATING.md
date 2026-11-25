# Updating and rolling back Orinoco

**Status: operator runbook for the preview Egg. Validate every step on a disposable Pterodactyl server before using it with important data.**

Orinoco does not update its own application image automatically. Pterodactyl controls the container image; the local Ollama model is managed separately. Keep the previous known-good image tag until the new release has passed its checks.

## Before an update

1. Confirm that the backup encryption key is available outside the VPS and configured in the Egg as `ORINOCO_BACKUP_KEY`.
2. Confirm that the backup scheduler's status file reports a recent successful backup:
   `/home/container/data/backups/.scheduler-status.json`.
3. Confirm that the corresponding `.oribak` file exists locally. If S3 upload is configured, confirm the status reports a verified upload and that the object exists in the private bucket.
4. Record the current container image tag, Egg settings, model name, and any environment-supplied secrets. The backup does not contain environment variables or Ollama model weights.
5. Do not proceed if the latest backup failed, cannot be verified, or its encryption key is unavailable.

The scheduler normally creates backups at 03:00 in the configured timezone and retains 14 days locally. For a critical upgrade, use a fresh backup rather than relying only on the previous night's copy.

## Creating a one-off backup with Pterodactyl

The Pterodactyl console is attached to Supervisor, not an interactive shell. To run a one-shot CLI command, temporarily change the server's **Startup Command** in the Panel to the command below, start the server, wait for the command to finish and record the backup path from its JSON output, then restore the normal startup command. The update helper creates the encrypted backup, verifies it and uploads it when S3 is configured:

```text
python -m orinoco.updates prepare
```

For verification, repeat with:

```text
python -m orinoco.backups verify /home/container/data/backups/your-backup-file.oribak
```

For an off-site upload, use:

```text
python -m orinoco.backups upload /home/container/data/backups/your-backup-file.oribak
```

These commands run as the normal unprivileged container user. Do not change the image or delete existing backups until the operation succeeds.

## Applying an application image update

1. Stop the Orinoco Pterodactyl server.
2. Keep a note of the current image tag so it can be restored if needed.
3. Change the server's Docker image to the exact new version tag supplied with the release. Do not guess a tag; use the tag published in that release's notes.
4. Keep the existing persistent server directory and Egg settings. Do not reinstall the server or delete its data directory.
5. Before starting Supervisor, temporarily set the **Startup Command** to the migration command below, using the fresh backup path created in the pre-update step. Start the server once and wait for the migration command to exit successfully:

If migration or its post-migration integrity checks fail, Orinoco now attempts to restore the verified pre-migration backup automatically while the application is stopped. Confirm the console explicitly reports that the backup was restored, then check the database and files before retrying. If the console says automatic restore also failed, do not start Supervisor; follow the manual restore procedure in the rollback section below.

```text
python -m orinoco.updates migrate --backup /home/container/data/backups/your-pre-update-backup.oribak
```

6. Restore the normal startup command:
   `supervisord -n -c /opt/orinoco/docker/supervisord.conf`.
7. Start the server and watch the Pterodactyl console for Supervisor, Ollama, model initialisation, web and backup-scheduler startup messages.
8. Check `/healthz` and `/readyz`. The first authenticated login also checks/initialises the SQLite schema as a fallback.
9. Sign in and check a chat reply, conversation history, personal memories, private documents, shared documents and web research (if configured).
10. Confirm the backup scheduler remains running and the next scheduled backup is recorded.

Do not change the Ollama model at the same time as an application update. Keeping those changes separate makes faults easier to diagnose.

## Rolling back

A newer application may have upgraded the SQLite schema. An older image intentionally refuses to open a database with a newer schema version. Restore the pre-update backup **before** starting the older image.

1. Stop the Orinoco server.
2. Make sure the previous image tag is available.
3. Ensure the encrypted backup file is present under `/home/container/data/backups`. If it is only in object storage, download it from the private bucket using the provider's authenticated tools; Orinoco's current CLI uploads but does not download remote backups.
4. Temporarily set the Panel's **Startup Command** to the restore command below, start the server once, and wait for the one-shot process to exit:

```text
python -m orinoco.backups restore /home/container/data/backups/your-backup-file.oribak --confirm
```

5. Restore the normal startup command:
   `supervisord -n -c /opt/orinoco/docker/supervisord.conf`.
6. Set the Docker image back to the previous known-good version tag and start Orinoco.
7. Check `/healthz`, `/readyz`, sign-in, chat, memories and documents. Keep the generated `.pre-restore` recovery copies until the restored installation has been checked.

The restore command validates the encrypted archive and SQLite integrity before replacing data. It leaves recovery copies of the previous database, document directory and file-based session secret. Restore must not run while the web application is active.

## Important recovery boundaries

- The backup encryption key is required to verify or restore a backup. Store it separately from the VPS and object-storage bucket.
- If `ORINOCO_SECRET_KEY` is supplied through the environment, preserve that value separately; it cannot be read back from the process environment for inclusion in a backup.
- S3 credentials and other Egg/environment variables are not included in the backup.
- Ollama model weights are excluded and must be downloaded again if the persistent model directory is lost.
- Local backup retention is automatic. Configure a separate lifecycle policy for remote bucket retention.
- A Pterodactyl backup stored on the same VPS is not an off-site recovery copy.

## Release gate

This runbook is not a substitute for a real rollback drill. Before a production release, test the full upgrade and rollback sequence on a disposable Panel server, including an actual restore of the database, documents and session secret. Do not publish the `stable` image until that test has passed.
