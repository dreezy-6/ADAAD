# SPDX-License-Identifier: Apache-2.0
"""Deterministic resource quota checks for sandbox execution."""

from __future__ import annotations

import sys
from typing import Dict


def rlimit_enforcement_supported() -> tuple[bool, str]:
    if not sys.platform.startswith(("linux", "darwin")):
        return False, "resource_quotas_platform"

    try:
        import resource
    except Exception:
        return False, "resource_quotas_no_resource_module"

    required = ("RLIMIT_CPU", "RLIMIT_AS", "RLIMIT_FSIZE")
    if any(not hasattr(resource, name) for name in required):
        return False, "resource_quotas_missing_rlimit"
    return True, "ok"


def build_rlimit_preexec_hook(*, cpu_limit_s: int, memory_limit_mb: int, disk_limit_mb: int):
    import resource

    memory_bytes = int(memory_limit_mb) * 1024 * 1024
    disk_bytes = int(disk_limit_mb) * 1024 * 1024

    def _apply_limits() -> None:
        resource.setrlimit(resource.RLIMIT_CPU, (int(cpu_limit_s), int(cpu_limit_s)))
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
        resource.setrlimit(resource.RLIMIT_FSIZE, (disk_bytes, disk_bytes))

    return _apply_limits


def enforce_resource_quotas(*, observed_cpu_s: float, observed_memory_mb: float, observed_disk_mb: float, observed_duration_s: float, cpu_limit_s: int, memory_limit_mb: int, disk_limit_mb: int, timeout_s: int) -> Dict[str, object]:
    cpu_ok = float(observed_cpu_s) <= float(cpu_limit_s)
    memory_ok = float(observed_memory_mb) <= float(memory_limit_mb)
    disk_ok = float(observed_disk_mb) <= float(disk_limit_mb)
    timeout_ok = float(observed_duration_s) <= float(timeout_s)
    passed = bool(cpu_ok and memory_ok and disk_ok and timeout_ok)
    return {
        "passed": passed,
        "cpu_ok": cpu_ok,
        "memory_ok": memory_ok,
        "disk_ok": disk_ok,
        "timeout_ok": timeout_ok,
        "observed": {
            "cpu_s": round(float(observed_cpu_s), 4),
            "memory_mb": round(float(observed_memory_mb), 4),
            "disk_mb": round(float(observed_disk_mb), 4),
            "duration_s": round(float(observed_duration_s), 4),
        },
    }


__all__ = ["build_rlimit_preexec_hook", "enforce_resource_quotas", "rlimit_enforcement_supported"]
