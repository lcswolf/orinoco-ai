"""Daily encrypted backup scheduler for the Orinoco container.

The scheduler runs as a supervised process. It creates one backup per local
calendar day, optionally uploads it to the configured private S3 destination,
and only prunes old local backups after the new backup has completed
successfully (including the remote upload when one is configured).
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import UTC, datetime, time as clock_time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from orinoco.backups import BackupError, create_backup, upload_backup

DEFAULT_BACKUP_ROOT = Path("/home/container/data/backups")
STATE_FILENAME = ".scheduler-status.json"
RETRY_INTERVAL_SECONDS = 15 * 60


def _settings() -> tuple[ZoneInfo, clock_time, int, Path]:
    """Read and validate the scheduler timezone, local run time and retention."""
    timezone_name = os.environ.get("TIMEZONE", "Europe/London").strip() or "Europe/London"
    try:
        timezone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"Unknown backup scheduler timezone: {timezone_name}") from exc

    raw_time = os.environ.get("ORINOCO_BACKUP_TIME", "03:00").strip()
    try:
        hour_text, minute_text = raw_time.split(":", maxsplit=1)
        scheduled_time = clock_time(int(hour_text), int(minute_text))
    except (ValueError, TypeError) as exc:
        raise ValueError("ORINOCO_BACKUP_TIME must use 24-hour HH:MM format.") from exc
    if len(hour_text) != 2 or len(minute_text) != 2:
        raise ValueError("ORINOCO_BACKUP_TIME must use 24-hour HH:MM format.")

    raw_retention = os.environ.get("ORINOCO_BACKUP_RETENTION_DAYS", "14").strip()
    try:
        retention_days = int(raw_retention)
    except ValueError as exc:
        raise ValueError("ORINOCO_BACKUP_RETENTION_DAYS must be a whole number.") from exc
    if not 1 <= retention_days <= 365:
        raise ValueError("ORINOCO_BACKUP_RETENTION_DAYS must be between 1 and 365.")

    backup_root = Path(
        os.environ.get("ORINOCO_BACKUP_PATH", str(DEFAULT_BACKUP_ROOT))
    ).expanduser()
    if backup_root.is_symlink():
        raise ValueError("The backup directory must not be a symbolic link.")
    return timezone, scheduled_time, retention_days, backup_root


def _read_state(state_path: Path) -> dict[str, object]:
    """Read scheduler progress, treating a missing or malformed file as empty state."""
    if state_path.is_symlink():
        raise BackupError("The backup scheduler status path must not be a symbolic link.")
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _parse_state_datetime(value: object, timezone: ZoneInfo) -> datetime | None:
    """Parse a persisted timestamp and normalise it to the scheduler timezone."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone)
    return parsed.astimezone(timezone)


def _last_success_local_date(state: dict[str, object], timezone: ZoneInfo) -> str | None:
    """Return the local calendar date of the last completed backup, if known."""
    completed = _parse_state_datetime(state.get("last_success_at"), timezone)
    return completed.date().isoformat() if completed is not None else None


def _retry_at(state: dict[str, object], timezone: ZoneInfo) -> datetime | None:
    """Return the next allowed retry time after the last recorded attempt."""
    attempted = _parse_state_datetime(state.get("last_attempt_at"), timezone)
    if attempted is None:
        return None
    return attempted + timedelta(seconds=RETRY_INTERVAL_SECONDS)


def _write_state(state_path: Path, state: dict[str, object]) -> None:
    """Atomically persist non-secret scheduler status with owner-only permissions."""
    if state_path.is_symlink():
        raise BackupError("The backup scheduler status path must not be a symbolic link.")
    temporary = state_path.with_name(state_path.name + ".tmp")
    if temporary.is_symlink():
        raise BackupError("The backup scheduler temporary path must not be a symbolic link.")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, state_path)
    try:
        state_path.chmod(0o600)
    except OSError:
        pass


def prune_local_backups(backup_root: Path, retention_days: int, *, now: datetime | None = None) -> int:
    """Delete only old regular encrypted backup files, never links or status files."""
    if not 1 <= retention_days <= 365:
        raise ValueError("Backup retention must be between 1 and 365 days.")
    if backup_root.is_symlink():
        raise BackupError("The backup directory must not be a symbolic link.")
    if not backup_root.exists():
        return 0
    current = now or datetime.now(UTC)
    cutoff = current.timestamp() - retention_days * 24 * 60 * 60
    removed = 0
    for candidate in backup_root.glob("orinoco-*.oribak"):
        # Do not follow a symlink even if it points to a file inside the backup folder.
        if candidate.is_symlink() or not candidate.is_file():
            continue
        try:
            if candidate.stat(follow_symlinks=False).st_mtime < cutoff:
                candidate.unlink()
                removed += 1
        except FileNotFoundError:
            # Another maintenance process may have removed it after the glob.
            continue
    return removed


def run_backup_cycle(
    *,
    timezone: ZoneInfo,
    retention_days: int,
    backup_root: Path,
    now: datetime | None = None,
) -> dict[str, object]:
    """Create, optionally upload and retain backups; persist success or failure status."""
    local_now = (now or datetime.now(UTC)).astimezone(timezone)
    state_path = backup_root / STATE_FILENAME
    if backup_root.is_symlink():
        raise BackupError("The backup directory must not be a symbolic link.")
    backup_root.mkdir(parents=True, exist_ok=True)
    try:
        backup_root.chmod(0o700)
    except OSError:
        pass

    state = _read_state(state_path)
    state["last_attempt_at"] = local_now.isoformat()
    state["last_error"] = None
    _write_state(state_path, state)

    try:
        backup_path = create_backup()
        state["last_backup"] = backup_path.name
        state["last_upload"] = None

        # An empty endpoint means local-only backups. A partially configured
        # endpoint is passed to the upload validator and reported as a failure.
        if os.environ.get("ORINOCO_BACKUP_S3_ENDPOINT", "").strip():
            upload_result = upload_backup(backup_path)
            state["last_upload"] = {
                "bucket": upload_result["bucket"],
                "key": upload_result["key"],
                "verified": upload_result["verified"],
            }

        removed = prune_local_backups(backup_root, retention_days, now=local_now)
        state["last_pruned_count"] = removed
        # A calendar day is complete only after the entire backup cycle,
        # including any configured off-site verification and local pruning.
        state["last_run_local_date"] = local_now.date().isoformat()
        state["last_success_at"] = local_now.astimezone(UTC).isoformat()
        state["last_error"] = None
        print(
            f"Orinoco backup scheduler: completed {backup_path.name}; "
            f"removed {removed} expired local backup(s).",
            flush=True,
        )
    except Exception as exc:
        # Retain the newly created local file and all older backups if remote
        # upload or verification fails. The error is visible in logs and status.
        state["last_error"] = f"{type(exc).__name__}: {exc}"[:1000]
        print(f"Orinoco backup scheduler: backup failed: {state['last_error']}", file=sys.stderr, flush=True)

    _write_state(state_path, state)
    return state


def main() -> int:
    """Run the daily scheduler until Supervisor stops the process."""
    try:
        timezone, scheduled_time, retention_days, backup_root = _settings()
    except ValueError as exc:
        print(f"Orinoco backup scheduler configuration error: {exc}", file=sys.stderr, flush=True)
        return 2

    print(
        f"Orinoco backup scheduler: daily at {scheduled_time:%H:%M} "
        f"({timezone.key}); local retention {retention_days} days.",
        flush=True,
    )
    state_path = backup_root / STATE_FILENAME

    while True:
        now = datetime.now(timezone)
        state = _read_state(state_path)
        already_succeeded_today = (
            _last_success_local_date(state, timezone) == now.date().isoformat()
        )
        scheduled_today = datetime.combine(now.date(), scheduled_time, tzinfo=timezone)

        # If the container starts after today's scheduled time, catch up. A
        # failed or interrupted attempt is retried after a short backoff rather
        # than incorrectly marking the calendar day as complete.
        if not already_succeeded_today and now >= scheduled_today:
            retry_at = _retry_at(state, timezone)
            if retry_at is None or now >= retry_at:
                run_backup_cycle(
                    timezone=timezone,
                    retention_days=retention_days,
                    backup_root=backup_root,
                    now=now,
                )
                time.sleep(30)
                continue
            next_run = retry_at
        else:
            next_run = scheduled_today if now < scheduled_today else scheduled_today + timedelta(days=1)
        seconds_until_run = max(1, min(60, int((next_run - now).total_seconds())))
        time.sleep(seconds_until_run)


if __name__ == "__main__":
    raise SystemExit(main())
