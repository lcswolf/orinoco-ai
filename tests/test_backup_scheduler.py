"""Tests for daily backup scheduling, retention and failure reporting."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from orinoco import backup_scheduler
from orinoco.backups import BackupError


def test_scheduler_defaults_to_uk_three_am_and_fourteen_day_retention(monkeypatch, tmp_path) -> None:
    """The default schedule follows UK local time and keeps a two-week local window."""
    monkeypatch.delenv("TIMEZONE", raising=False)
    monkeypatch.delenv("ORINOCO_BACKUP_TIME", raising=False)
    monkeypatch.delenv("ORINOCO_BACKUP_RETENTION_DAYS", raising=False)
    monkeypatch.setenv("ORINOCO_BACKUP_PATH", str(tmp_path / "backups"))

    timezone, scheduled_time, retention, root = backup_scheduler._settings()

    assert timezone.key == "Europe/London"
    assert scheduled_time.strftime("%H:%M") == "03:00"
    assert retention == 14
    assert root == tmp_path / "backups"


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("ORINOCO_BACKUP_TIME", "3am"),
        ("ORINOCO_BACKUP_TIME", "25:00"),
        ("ORINOCO_BACKUP_RETENTION_DAYS", "0"),
        ("ORINOCO_BACKUP_RETENTION_DAYS", "366"),
        ("TIMEZONE", "Not/A_Timezone"),
    ],
)
def test_scheduler_rejects_invalid_configuration(monkeypatch, variable, value) -> None:
    """Invalid schedules must fail clearly instead of silently changing retention."""
    monkeypatch.setenv(variable, value)
    with pytest.raises(ValueError):
        backup_scheduler._settings()


def test_scheduler_creates_backup_and_records_success(tmp_path, monkeypatch) -> None:
    """A successful local backup is recorded in a readable private status file."""
    backup_root = tmp_path / "backups"
    monkeypatch.setenv("ORINOCO_BACKUP_PATH", str(backup_root))
    monkeypatch.delenv("ORINOCO_BACKUP_S3_ENDPOINT", raising=False)
    created = backup_root / "orinoco-20261124T030000Z.oribak"

    def fake_create_backup():
        created.parent.mkdir(parents=True, exist_ok=True)
        created.write_bytes(b"encrypted backup")
        return created

    monkeypatch.setattr(backup_scheduler, "create_backup", fake_create_backup)
    now = datetime(2026, 11, 24, 3, 0, tzinfo=ZoneInfo("Europe/London"))
    state = backup_scheduler.run_backup_cycle(
        timezone=ZoneInfo("Europe/London"),
        retention_days=14,
        backup_root=backup_root,
        now=now,
    )

    status_path = backup_root / backup_scheduler.STATE_FILENAME
    assert state["last_run_local_date"] == "2026-11-24"
    assert state["last_backup"] == created.name
    assert state["last_error"] is None
    assert json.loads(status_path.read_text(encoding="utf-8"))["last_backup"] == created.name
    assert status_path.stat().st_mode & 0o777 == 0o600


def test_failed_remote_upload_keeps_new_and_old_local_backups(tmp_path, monkeypatch) -> None:
    """A failed off-site upload must not trigger retention cleanup."""
    backup_root = tmp_path / "backups"
    backup_root.mkdir()
    monkeypatch.setenv("ORINOCO_BACKUP_PATH", str(backup_root))
    monkeypatch.setenv("ORINOCO_BACKUP_S3_ENDPOINT", "https://objects.example.test")
    old = backup_root / "orinoco-old.oribak"
    old.write_bytes(b"old encrypted backup")
    os.utime(old, (0, 0))
    created = backup_root / "orinoco-20261124T030000Z.oribak"

    def fake_create_backup():
        created.write_bytes(b"new encrypted backup")
        return created

    def fail_upload(path):
        raise BackupError("simulated object-storage outage")

    monkeypatch.setattr(backup_scheduler, "create_backup", fake_create_backup)
    monkeypatch.setattr(backup_scheduler, "upload_backup", fail_upload)
    state = backup_scheduler.run_backup_cycle(
        timezone=ZoneInfo("Europe/London"),
        retention_days=14,
        backup_root=backup_root,
        now=datetime(2026, 11, 24, 3, 0, tzinfo=ZoneInfo("Europe/London")),
    )

    assert "simulated object-storage outage" in state["last_error"]
    assert old.exists()
    assert created.exists()


def test_retention_only_removes_old_regular_orinoco_backup_files(tmp_path) -> None:
    """Retention must leave recent files, unrelated files and symbolic links alone."""
    backup_root = tmp_path / "backups"
    backup_root.mkdir()
    old = backup_root / "orinoco-old.oribak"
    recent = backup_root / "orinoco-recent.oribak"
    unrelated = backup_root / "important.txt"
    outside = tmp_path / "outside.oribak"
    for path in (old, recent, unrelated, outside):
        path.write_bytes(b"data")
    now = datetime.now(UTC)
    os.utime(old, (now.timestamp() - 30 * 86400, now.timestamp() - 30 * 86400))
    link = backup_root / "orinoco-linked.oribak"
    link.symlink_to(outside)

    removed = backup_scheduler.prune_local_backups(backup_root, 14, now=now)

    assert removed == 1
    assert not old.exists()
    assert recent.exists()
    assert unrelated.exists()
    assert link.is_symlink()
    assert outside.exists()
