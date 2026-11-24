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


def test_document_path_resolver_rejects_traversal_and_symlinks(tmp_path, monkeypatch) -> None:
    """Stored document paths must not escape the private root or follow links."""
    import pytest

    root = tmp_path / "documents"
    root.mkdir()
    target = tmp_path / "private-target.txt"
    target.write_text("keep", encoding="utf-8")
    (root / "linked.txt").symlink_to(target)
    monkeypatch.setenv("ORINOCO_DOCUMENTS_PATH", str(root))

    with pytest.raises(ValueError, match="invalid document storage path"):
        storage.resolve_document_path("../private-target.txt")
    with pytest.raises(ValueError, match="symbolic links"):
        storage.resolve_document_path("linked.txt")
    assert target.read_text(encoding="utf-8") == "keep"
