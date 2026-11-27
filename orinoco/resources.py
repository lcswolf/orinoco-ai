"""Container-aware CPU and memory discovery for safe local inference defaults."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class ResourceProfile:
    """The CPU and memory limits visible to the Orinoco container."""

    cpu_count: int
    memory_limit_bytes: int | None
    memory_current_bytes: int | None

    @property
    def memory_available_bytes(self) -> int | None:
        """Return remaining cgroup memory when both limit and usage are known."""
        if self.memory_limit_bytes is None or self.memory_current_bytes is None:
            return None
        return max(0, self.memory_limit_bytes - self.memory_current_bytes)

    def as_dict(self) -> dict[str, int | None]:
        """Return safe, serialisable resource metadata for local diagnostics."""
        return asdict(self) | {"memory_available_bytes": self.memory_available_bytes}


def parse_cpuset(value: str) -> int | None:
    """Count CPUs in Linux cpuset syntax, such as '0-3,6'; reject malformed input."""
    value = value.strip()
    if not value:
        return None
    cpus: set[int] = set()
    try:
        for part in value.split(","):
            if "-" in part:
                start_text, end_text = part.split("-", 1)
                start, end = int(start_text), int(end_text)
                if start < 0 or end < start or end - start > 4096:
                    return None
                cpus.update(range(start, end + 1))
            else:
                cpu = int(part)
                if cpu < 0:
                    return None
                cpus.add(cpu)
    except ValueError:
        return None
    return len(cpus) or None


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="ascii").strip()
    except (OSError, UnicodeError):
        return None


def _positive_int(value: str | None) -> int | None:
    if value is None or not value.isdigit():
        return None
    parsed = int(value)
    return parsed if parsed > 0 else None


def _cpu_quota_count(root: Path) -> int | None:
    """Read cgroup v2 or v1 CPU quota and round down to avoid oversubscription."""
    fields = (_read(root / "cpu.max") or "").split()
    if len(fields) == 2 and fields[0] != "max":
        quota, period = _positive_int(fields[0]), _positive_int(fields[1])
        if quota is not None and period is not None:
            return max(1, quota // period)

    quota = _read(root / "cpu" / "cpu.cfs_quota_us")
    period = _read(root / "cpu" / "cpu.cfs_period_us")
    if quota is not None and quota.isdigit() and int(quota) > 0:
        period_value = _positive_int(period)
        if period_value is not None:
            return max(1, int(quota) // period_value)
    return None


def _memory_values(root: Path) -> tuple[int | None, int | None]:
    """Read cgroup v2 or v1 memory limit and current usage, ignoring unlimited sentinels."""
    limit = _positive_int(_read(root / "memory.max"))
    current = _positive_int(_read(root / "memory.current"))
    if limit is not None and limit < (1 << 60):
        return limit, current

    limit = _positive_int(_read(root / "memory" / "memory.limit_in_bytes"))
    current = _positive_int(_read(root / "memory" / "memory.usage_in_bytes"))
    if limit is not None and limit < (1 << 60):
        return limit, current
    return None, None


def detect_resources(
    *,
    cgroup_root: Path = Path("/sys/fs/cgroup"),
    host_cpu_count: int | None = None,
    affinity_cpu_count: int | None = None,
) -> ResourceProfile:
    """Detect effective CPUs and cgroup memory without assuming host resources are available."""
    host_count = max(1, host_cpu_count or os.cpu_count() or 1)
    limits = [host_count]

    if affinity_cpu_count is None:
        try:
            affinity_cpu_count = len(os.sched_getaffinity(0))
        except (AttributeError, OSError):
            affinity_cpu_count = None
    if affinity_cpu_count is not None and affinity_cpu_count > 0:
        limits.append(affinity_cpu_count)

    cpuset_text = _read(cgroup_root / "cpuset.cpus.effective")
    if cpuset_text is None:
        cpuset_text = _read(cgroup_root / "cpuset" / "cpuset.cpus")
    cpuset_count = parse_cpuset(cpuset_text) if cpuset_text is not None else None
    if cpuset_count is not None:
        limits.append(cpuset_count)

    quota_count = _cpu_quota_count(cgroup_root)
    if quota_count is not None:
        limits.append(quota_count)

    memory_limit, memory_current = _memory_values(cgroup_root)
    return ResourceProfile(
        cpu_count=max(1, min(limits)),
        memory_limit_bytes=memory_limit,
        memory_current_bytes=memory_current,
    )


@lru_cache(maxsize=1)
def get_resource_profile() -> ResourceProfile:
    """Cache the container resource profile once per application process."""
    return detect_resources()


def resolve_ai_threads(
    profile: ResourceProfile | None = None,
    *,
    configured: str | None = None,
) -> int:
    """Resolve AI_THREADS: zero means auto; a positive value can lower, not exceed, detected CPUs."""
    selected = os.environ.get("AI_THREADS", "0") if configured is None else configured
    if not selected.isdigit() or int(selected) > 64:
        raise ValueError("AI_THREADS must be an integer between 0 and 64.")
    requested = int(selected)
    available = (profile or get_resource_profile()).cpu_count
    return available if requested == 0 else min(requested, available)
