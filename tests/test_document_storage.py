"""Tests for cross-platform document storage coordination."""

import sys
from types import SimpleNamespace

from orinoco.documents import storage


def test_windows_locking_fallback_uses_byte_range_lock(tmp_path, monkeypatch) -> None:
    """Exercise the msvcrt branch without requiring a Windows CI runner."""
    calls = []
    fake_msvcrt = SimpleNamespace(
        LK_LOCK=1,
        LK_UNLCK=2,
        locking=lambda descriptor, mode, count: calls.append((mode, count)),
    )
    monkeypatch.setattr(storage, "fcntl", None)
    monkeypatch.setitem(sys.modules, "msvcrt", fake_msvcrt)
    monkeypatch.setenv("ORINOCO_DOCUMENTS_PATH", str(tmp_path / "documents"))

    with storage.document_storage_lock():
        pass

    assert calls == [(fake_msvcrt.LK_LOCK, 1), (fake_msvcrt.LK_UNLCK, 1)]
    assert (tmp_path / ".documents.lock").read_bytes() == b"\0"
