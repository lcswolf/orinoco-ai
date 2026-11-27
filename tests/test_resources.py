"""Tests for cgroup-aware CPU and memory detection."""

from pathlib import Path

import pytest

from orinoco.resources import detect_resources, parse_cpuset, resolve_ai_threads


def _write(root: Path, relative: str, value: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="ascii")


def test_parse_cpuset_ranges_and_reject_malformed_values() -> None:
    assert parse_cpuset("0-3,6,8-9") == 7
    assert parse_cpuset("") is None
    assert parse_cpuset("3-1") is None
    assert parse_cpuset("0-99999") is None
    assert parse_cpuset("0,x") is None


def test_detects_cgroup_v2_cpu_quota_cpuset_and_memory(tmp_path: Path) -> None:
    _write(tmp_path, "cpu.max", "250000 100000")
    _write(tmp_path, "cpuset.cpus.effective", "0-3,6")
    _write(tmp_path, "memory.max", str(4 * 1024**3))
    _write(tmp_path, "memory.current", str(1024**3))

    profile = detect_resources(
        cgroup_root=tmp_path,
        host_cpu_count=8,
        affinity_cpu_count=6,
    )

    assert profile.cpu_count == 2
    assert profile.memory_limit_bytes == 4 * 1024**3
    assert profile.memory_current_bytes == 1024**3
    assert profile.memory_available_bytes == 3 * 1024**3


def test_detects_cgroup_v1_limits(tmp_path: Path) -> None:
    _write(tmp_path, "cpu/cpu.cfs_quota_us", "150000")
    _write(tmp_path, "cpu/cpu.cfs_period_us", "100000")
    _write(tmp_path, "cpuset/cpuset.cpus", "0-2,5")
    _write(tmp_path, "memory/memory.limit_in_bytes", str(2 * 1024**3))
    _write(tmp_path, "memory/memory.usage_in_bytes", str(512 * 1024**2))

    profile = detect_resources(
        cgroup_root=tmp_path,
        host_cpu_count=8,
        affinity_cpu_count=6,
    )

    assert profile.cpu_count == 1
    assert profile.memory_limit_bytes == 2 * 1024**3
    assert profile.memory_available_bytes == (2 * 1024**3) - (512 * 1024**2)


def test_unlimited_cgroup_memory_does_not_look_like_a_real_limit(tmp_path: Path) -> None:
    _write(tmp_path, "memory.max", "max")
    _write(tmp_path, "memory.current", "123456")

    profile = detect_resources(
        cgroup_root=tmp_path,
        host_cpu_count=6,
        affinity_cpu_count=4,
    )

    assert profile.cpu_count == 4
    assert profile.memory_limit_bytes is None
    assert profile.memory_current_bytes is None


def test_falls_back_to_affinity_and_host_cpu_count_when_cgroups_are_unavailable(tmp_path: Path) -> None:
    assert detect_resources(
        cgroup_root=tmp_path,
        host_cpu_count=6,
        affinity_cpu_count=3,
    ).cpu_count == 3
    assert detect_resources(
        cgroup_root=tmp_path,
        host_cpu_count=6,
        affinity_cpu_count=None,
    ).cpu_count == 6


def test_ai_threads_auto_uses_detected_count_and_override_only_reduces_it() -> None:
    profile = detect_resources(host_cpu_count=6, affinity_cpu_count=4, cgroup_root=Path("/nonexistent"))
    assert resolve_ai_threads(profile, configured="0") == 4
    assert resolve_ai_threads(profile, configured="2") == 2
    assert resolve_ai_threads(profile, configured="8") == 4


@pytest.mark.parametrize("value", ["", "-1", "65", "auto", "1.5"])
def test_ai_threads_rejects_invalid_values(value: str) -> None:
    profile = detect_resources(host_cpu_count=4, affinity_cpu_count=4, cgroup_root=Path("/nonexistent"))
    with pytest.raises(ValueError, match="AI_THREADS"):
        resolve_ai_threads(profile, configured=value)
