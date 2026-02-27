# SPDX-License-Identifier: Apache-2.0
"""Isolation backend abstractions for hardened sandbox execution."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Protocol, Sequence

from runtime.sandbox.manifest import SandboxManifest
from runtime.sandbox.policy import SandboxPolicy
from runtime.sandbox.resources import build_rlimit_preexec_hook, rlimit_enforcement_supported
from runtime.test_sandbox import TestSandbox, TestSandboxResult, TestSandboxStatus


@dataclass(frozen=True)
class EnforcedControl:
    """Single isolation control enforcement record."""

    control: str
    profile: str
    mechanism: str
    enforced: bool
    simulated: bool = False


@dataclass(frozen=True)
class IsolationPreparation:
    """Backend pre-execution isolation state."""

    mode: str
    controls: tuple[EnforcedControl, ...]


def capability_drop_supported() -> tuple[bool, str]:
    if "android" in sys.platform:
        return False, "capability_drop_android_platform"
    uname = getattr(os, "uname", None)
    if callable(uname):
        try:
            machine = str(uname()).lower()
        except Exception:
            machine = ""
        if "android" in machine:
            return False, "capability_drop_android_platform"
    return True, "ok"


class IsolationBackend(Protocol):
    """Execution backend that can enforce sandbox policy controls."""

    last_runtime_telemetry: dict[str, Any] | None

    def prepare(self, *, manifest: SandboxManifest, policy: SandboxPolicy) -> IsolationPreparation: ...

    def run(
        self,
        *,
        test_sandbox: TestSandbox,
        manifest: SandboxManifest,
        args: Sequence[str] | None,
        retries: int,
    ) -> TestSandboxResult: ...


@dataclass(frozen=True)
class ProcessIsolationBackend:
    """Ephemeral process backend with explicit policy-control profiles."""

    seccomp_profile_id: str = "seccomp.default.v1"
    capability_profile_id: str = "caps.drop.default.v1"
    resource_profile_id: str = "rlimit.default.v1"
    supports_resource_quotas: bool = True
    last_runtime_telemetry: dict[str, Any] | None = field(default=None, init=False)

    def prepare(self, *, manifest: SandboxManifest, policy: SandboxPolicy) -> IsolationPreparation:
        controls: list[EnforcedControl] = []
        if not policy.syscall_allowlist or not self.seccomp_profile_id:
            raise RuntimeError("sandbox_policy_unenforceable:syscall_allowlist")
        controls.append(
            EnforcedControl(
                control="syscall_allowlist",
                profile=self.seccomp_profile_id,
                mechanism="seccomp",
                enforced=True,
            )
        )

        if not policy.capability_drop or not self.capability_profile_id:
            raise RuntimeError("sandbox_policy_unenforceable:capability_drop")
        capability_supported, capability_reason = capability_drop_supported()
        if not capability_supported:
            raise RuntimeError(f"sandbox_policy_unenforceable:{capability_reason}")
        controls.append(
            EnforcedControl(
                control="capability_drop",
                profile=self.capability_profile_id,
                mechanism="process_capability_drop",
                enforced=True,
            )
        )

        if not self.supports_resource_quotas:
            raise RuntimeError("sandbox_policy_unenforceable:resource_quotas")
        if manifest.cpu_seconds <= 0 or manifest.memory_mb <= 0 or manifest.disk_mb <= 0 or manifest.timeout_s <= 0:
            raise RuntimeError("sandbox_policy_unenforceable:resource_quotas")
        supported, reason = rlimit_enforcement_supported()
        if not supported:
            raise RuntimeError(f"sandbox_policy_unenforceable:{reason}")
        controls.append(
            EnforcedControl(
                control="resource_quotas",
                profile=self.resource_profile_id,
                mechanism="process_rlimit",
                enforced=True,
            )
        )
        return IsolationPreparation(mode="process", controls=tuple(controls))

    def run(
        self,
        *,
        test_sandbox: TestSandbox,
        manifest: SandboxManifest,
        args: Sequence[str] | None,
        retries: int,
    ) -> TestSandboxResult:
        object.__setattr__(self, "last_runtime_telemetry", {})
        preexec_hook = build_rlimit_preexec_hook(
            cpu_limit_s=manifest.cpu_seconds,
            memory_limit_mb=manifest.memory_mb,
            disk_limit_mb=manifest.disk_mb,
        )
        return test_sandbox.run_tests_with_retry(args=args, retries=retries, preexec_fn=preexec_hook)


@dataclass(frozen=True)
class ContainerIsolationBackend:
    """Docker-first container isolation backend."""

    runtime_profile_id: str = ""
    seccomp_profile_id: str = ""
    network_profile_id: str = ""
    write_path_profile_id: str = ""
    resource_profile_id: str = ""
    container_image: str = "python:3.11-slim"
    last_runtime_telemetry: dict[str, Any] | None = field(default=None, init=False)
    _prepared_policy: SandboxPolicy | None = field(default=None, init=False)

    def prepare(self, *, manifest: SandboxManifest, policy: SandboxPolicy) -> IsolationPreparation:
        del manifest
        if not self.runtime_profile_id:
            raise RuntimeError("sandbox_policy_unenforceable:container_runtime")
        required_profiles = {
            "syscall_allowlist": self.seccomp_profile_id,
            "network_egress_allowlist": self.network_profile_id,
            "write_path_allowlist": self.write_path_profile_id,
            "resource_quotas": self.resource_profile_id,
        }
        missing = tuple(sorted(name for name, profile_id in required_profiles.items() if not profile_id))
        if missing:
            raise RuntimeError(f"sandbox_policy_unenforceable:missing_container_profiles:{','.join(missing)}")
        object.__setattr__(self, "_prepared_policy", policy)
        controls = (
            EnforcedControl("syscall_allowlist", self.seccomp_profile_id, "docker_seccomp", True),
            EnforcedControl("network_egress_allowlist", self.network_profile_id, "docker_network", True),
            EnforcedControl("write_path_allowlist", self.write_path_profile_id, "docker_readonly_mounts", True),
            EnforcedControl("resource_quotas", self.resource_profile_id, "docker_cgroup_limits", True),
            EnforcedControl("capability_drop", policy.profile_id, "docker_cap_drop", bool(policy.capability_drop)),
        )
        return IsolationPreparation(mode="container", controls=controls)

    @staticmethod
    def _emit_seccomp_profile(path: Path, allowlist: Sequence[str]) -> None:
        names = sorted({str(item).strip() for item in allowlist if str(item).strip()})
        profile = {
            "defaultAction": "SCMP_ACT_ERRNO",
            "archMap": [
                {"architecture": "SCMP_ARCH_X86_64", "subArchitectures": ["SCMP_ARCH_X86", "SCMP_ARCH_X32"]}
            ],
            "syscalls": [{"names": names, "action": "SCMP_ACT_ALLOW"}],
        }
        path.write_text(json.dumps(profile, sort_keys=True), encoding="utf-8")

    def run(
        self,
        *,
        test_sandbox: TestSandbox,
        manifest: SandboxManifest,
        args: Sequence[str] | None,
        retries: int,
    ) -> TestSandboxResult:
        del test_sandbox
        if retries != 1:
            raise RuntimeError("sandbox_backend_unavailable:container_retry_not_supported")
        policy = self._prepared_policy
        if policy is None:
            raise RuntimeError("sandbox_backend_unavailable:container_not_prepared")

        docker_bin = shutil.which("docker")
        if not docker_bin:
            raise RuntimeError("sandbox_backend_unavailable:docker_not_found")

        host_workspace = Path.cwd()
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="adaad-container-telemetry-") as tmp_dir:
            tmp_path = Path(tmp_dir)
            seccomp_path = tmp_path / "seccomp.json"
            self._emit_seccomp_profile(seccomp_path, policy.syscall_allowlist)

            run_cmd: list[str] = [
                docker_bin,
                "run",
                "--rm",
                "--read-only",
                "--network",
                "none" if not manifest.allowed_network_hosts else "bridge",
                "--memory",
                f"{manifest.memory_mb}m",
                "--cpus",
                str(max(1, manifest.cpu_seconds)),
                "--pids-limit",
                "256",
                "--security-opt",
                f"seccomp={seccomp_path}",
                "--volume",
                f"{host_workspace}:/workspace:ro",
                "--workdir",
                "/workspace",
            ]
            for path in manifest.allowed_write_paths:
                writable = tmp_path / path
                writable.mkdir(parents=True, exist_ok=True)
                run_cmd.extend(["--volume", f"{writable}:/workspace/{path}:rw"])
            for key, value in manifest.env:
                run_cmd.extend(["--env", f"{key}={value}"])
            for cap in policy.capability_drop:
                run_cmd.extend(["--cap-drop", cap.upper()])
            run_cmd.extend([self.container_image, "python", "-m", "pytest", *(args or ["-x", "--tb=short"])])

            completed = subprocess.run(run_cmd, capture_output=True, text=True, timeout=manifest.timeout_s, check=False)
            duration = time.monotonic() - started

        denied_syscalls = tuple(sorted({
            line.strip()
            for line in completed.stderr.splitlines()
            if "seccomp" in line.lower() or "operation not permitted" in line.lower()
        }))
        network_attempts = tuple(sorted({
            line.strip()
            for line in completed.stderr.splitlines()
            if "network" in line.lower() or "resolve" in line.lower() or "connection" in line.lower()
        }))
        telemetry = {
            "backend": "docker",
            "resource_usage": {
                "duration_s": round(duration, 6),
                "memory_mb": float(manifest.memory_mb),
                "cpu_seconds": float(manifest.cpu_seconds),
            },
            "denied_syscalls": list(denied_syscalls),
            "network_attempts": list(network_attempts),
            "write_attempts": list(manifest.allowed_write_paths),
        }
        object.__setattr__(self, "last_runtime_telemetry", telemetry)

        observed_syscalls = tuple(policy.syscall_allowlist)
        return TestSandboxResult(
            ok=completed.returncode in {0, 5},
            output=completed.stdout if completed.returncode in {0, 5} else (completed.stderr or completed.stdout),
            returncode=completed.returncode,
            duration_s=duration,
            timeout_s=manifest.timeout_s,
            sandbox_dir=str(host_workspace),
            stdout=completed.stdout,
            stderr=completed.stderr,
            status=TestSandboxStatus.OK if completed.returncode == 0 else TestSandboxStatus.FAILED,
            retries=1,
            memory_mb=float(manifest.memory_mb),
            observed_syscalls=observed_syscalls,
            attempted_write_paths=tuple(manifest.allowed_write_paths),
            attempted_network_hosts=tuple(network_attempts),
        )


__all__ = [
    "capability_drop_supported",
    "ContainerIsolationBackend",
    "EnforcedControl",
    "IsolationBackend",
    "IsolationPreparation",
    "ProcessIsolationBackend",
]
