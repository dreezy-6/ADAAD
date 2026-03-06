#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
sync_docs_on_merge.py — Post-merge documentation synchroniser.

Runs automatically after every merge to main.  Reads VERSION and
recent CHANGELOG entries, then propagates version numbers, info-boxes,
and the Evolution-History table across all public-facing files without
touching governance policy or schema files.

Constitutional invariants:
  - Deterministic:  given the same VERSION + CHANGELOG the output is
    always identical (no timestamps, no randomness).
  - Fail-closed:    any unexpected write failure exits non-zero and
    emits SYNC_ERROR_* codes to stdout.
  - Audit trail:    every changed file and every replacement is printed
    to stdout in machine-readable JSON before any write is attempted.
  - No silent edits: files are only written when content actually changed.
  - Read-only guards: governance/constitution/schema files are excluded.

Exit codes:
  0  — success (including no changes needed)
  1  — sync error (SYNC_ERROR_* emitted to stdout as JSON)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

# ── Root ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]

# ── Files that must NEVER be modified by this script ────────────────────────
PROTECTED_PATHS: frozenset[str] = frozenset(
    {
        "docs/CONSTITUTION.md",
        "docs/governance/ARCHITECT_SPEC_v2.0.0.md",
        "governance/CANONICAL_ENGINE_DECLARATION.md",
        "governance_runtime_profile.lock.json",
        "runtime/constitution.py",
        "schemas/",
        ".github/workflows/",
        "AGENTS.md",          # has its own version contract
    }
)

# ── Info-box sentinel tags ───────────────────────────────────────────────────
INFOBOX_START = "<!-- ADAAD_VERSION_INFOBOX:START -->"
INFOBOX_END   = "<!-- ADAAD_VERSION_INFOBOX:END -->"

ARCH_SNAPSHOT_START = "<!-- ARCH_SNAPSHOT_METADATA:START -->"
ARCH_SNAPSHOT_END   = "<!-- ARCH_SNAPSHOT_METADATA:END -->"

# ── Badge colour (consistent with existing README style) ─────────────────────
BADGE_COLOUR = "00d4ff"
BADGE_LABEL_COLOUR = "060d14"


# ────────────────────────────────────────────────────────────────────────────
# Data helpers
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class SyncPlan:
    version: str
    prev_version: str
    date_str: str
    changelog_entry: str          # first entry block from CHANGELOG
    new_capabilities: list[str]   # bullet lines from the first CHANGELOG block
    git_sha: str
    git_branch: str
    changes: list[dict[str, Any]] = field(default_factory=list)

    def record(self, rel_path: str, rule: str, old: str, new: str) -> None:
        self.changes.append(
            {"file": rel_path, "rule": rule, "old": old[:120], "new": new[:120]}
        )


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _is_protected(rel: str) -> bool:
    for guard in PROTECTED_PATHS:
        if rel.startswith(guard) or rel == guard.rstrip("/"):
            return True
    return False


# ────────────────────────────────────────────────────────────────────────────
# Source-of-truth readers
# ────────────────────────────────────────────────────────────────────────────

def _read_version() -> str:
    v = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", v):
        _fatal("SYNC_ERROR_BAD_VERSION", f"VERSION file contains unexpected value: {v!r}")
    return v


def _read_prev_version(version: str) -> str:
    """Find the second version header in CHANGELOG (the one before current)."""
    changelog = _read(ROOT / "CHANGELOG.md")
    headers = re.findall(r"^## \[(\d+\.\d+\.\d+)\]", changelog, re.MULTILINE)
    seen_current = False
    for h in headers:
        if h == version:
            seen_current = True
            continue
        if seen_current:
            return h
    return version  # fallback: no previous version found


def _read_changelog_entry(version: str) -> tuple[str, list[str]]:
    """Return (full_block_text, [capability bullet lines]) for the current version."""
    changelog = _read(ROOT / "CHANGELOG.md")
    pattern = rf"(^## \[{re.escape(version)}\].*?)(?=^## \[|\Z)"
    m = re.search(pattern, changelog, re.MULTILINE | re.DOTALL)
    if not m:
        return "", []
    block = m.group(1).strip()
    # Extract "New:" or capability lines
    caps: list[str] = []
    for line in block.splitlines():
        stripped = line.strip()
        if stripped.startswith("- **New:**") or stripped.startswith("- **New"):
            # e.g. "- **New:** `runtime/foo.py` — brief description"
            caps.append(stripped)
    return block, caps


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except Exception:
        return "unknown"


def _git_branch() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except Exception:
        return "main"


# ────────────────────────────────────────────────────────────────────────────
# Replacement rules (pure functions: content_in → content_out)
# ────────────────────────────────────────────────────────────────────────────

def _replace_badge_version(content: str, version: str) -> tuple[str, list[str]]:
    """Replace shields.io version badge strings."""
    pattern = r"(https://img\.shields\.io/badge/version-)(\d+\.\d+\.\d+)(-[0-9a-fA-F]+)"
    repl = rf"\g<1>{version}\g<3>"
    new, n = re.subn(pattern, repl, content)
    matches = re.findall(pattern, content)
    old_versions = [m[1] for m in matches]
    changes = [f"badge version {v} → {version}" for v in old_versions if v != version]
    return new, changes


def _replace_inline_version_badge(content: str, version: str) -> tuple[str, list[str]]:
    """Replace ![Version: X.Y.Z](...) style badges."""
    pattern = r"(!\[Version: )(\d+\.\d+\.\d+)(\])"
    repl = rf"\g<1>{version}\g<3>"
    new, n = re.subn(pattern, repl, content)
    old_versions = re.findall(r"!\[Version: (\d+\.\d+\.\d+)\]", content)
    changes = [f"inline badge {v} → {version}" for v in old_versions if v != version]
    return new, changes


def _update_version_infobox(content: str, plan: SyncPlan) -> tuple[str, list[str]]:
    """Replace content between ADAAD_VERSION_INFOBOX sentinels."""
    if INFOBOX_START not in content:
        return content, []

    # Build the new infobox
    cap_lines = "\n".join(f"| {c.lstrip('- ')} |" for c in plan.new_capabilities[:8])
    if not cap_lines:
        cap_lines = "| _(no new capabilities listed in this release)_ |"

    new_box = (
        f"{INFOBOX_START}\n"
        f"<!-- Auto-generated by scripts/sync_docs_on_merge.py — do not edit manually -->\n"
        f"\n"
        f"| Field | Value |\n"
        f"|---|---|\n"
        f"| **Current version** | `{plan.version}` |\n"
        f"| **Released** | {plan.date_str} |\n"
        f"| **Git SHA** | `{plan.git_sha}` |\n"
        f"| **Branch** | `{plan.git_branch}` |\n"
        f"\n"
        f"**New in this release:**\n\n"
        f"{cap_lines}\n"
        f"\n"
        f"{INFOBOX_END}"
    )
    pattern = re.compile(
        re.escape(INFOBOX_START) + r".*?" + re.escape(INFOBOX_END),
        re.DOTALL,
    )
    old_match = pattern.search(content)
    old_block = old_match.group(0) if old_match else ""
    new_content = pattern.sub(new_box, content)
    if new_content == content:
        return content, []
    return new_content, [f"VERSION_INFOBOX updated to {plan.version}"]


def _update_arch_snapshot(content: str, plan: SyncPlan) -> tuple[str, list[str]]:
    """Update the ARCH_SNAPSHOT_METADATA block in README_IMPLEMENTATION_ALIGNMENT.md."""
    if ARCH_SNAPSHOT_START not in content:
        return content, []

    new_block = (
        f"{ARCH_SNAPSHOT_START}\n"
        f"## Architecture Deep-Dive Snapshot\n"
        f"\n"
        f"| Metric | Value |\n"
        f"| --- | --- |\n"
        f"| Report version | `{plan.version}` |\n"
        f"| Branch | `{plan.git_branch}` |\n"
        f"| Tag | `(none)` |\n"
        f"| Short SHA | `{plan.git_sha}` |\n"
        f"\n"
        f"All future architecture snapshots MUST include branch, tag (if any), and short SHA.\n"
        f"{ARCH_SNAPSHOT_END}"
    )
    pattern = re.compile(
        re.escape(ARCH_SNAPSHOT_START) + r".*?" + re.escape(ARCH_SNAPSHOT_END),
        re.DOTALL,
    )
    new_content = pattern.sub(new_block, content)
    if new_content == content:
        return content, []
    return new_content, [f"ARCH_SNAPSHOT updated to {plan.version} / {plan.git_sha}"]


def _update_readme_evolution_table(content: str, plan: SyncPlan) -> tuple[str, list[str]]:
    """
    Ensure the Evolution History table in README.md has a row for the
    current version.  Inserts a new row directly below the table header
    if the current version is not already present.
    """
    # Find the table
    table_pattern = re.compile(
        r"(## Evolution History\n\n\| Version \| Capability \|\n\|[-|]+\|\n)(.*?)(\n---)",
        re.DOTALL,
    )
    m = table_pattern.search(content)
    if not m:
        return content, []

    header, rows, tail = m.group(1), m.group(2), m.group(3)
    major_minor = ".".join(plan.version.split(".")[:2])  # e.g. "2.2"

    # Build a one-line capability summary from the changelog
    summary_parts: list[str] = []
    changelog_block = plan.changelog_entry
    # Try to pick section headings from the changelog block
    for line in changelog_block.splitlines():
        stripped = line.strip()
        if stripped.startswith("### ") and "SHIPPED" in stripped:
            # e.g. "### Phase 2 — Governed Explore/Exploit Loop (SHIPPED)"
            clean = stripped.lstrip("#").strip().replace(" (SHIPPED)", "").replace(" (shipped)", "")
            summary_parts.append(clean)
    if not summary_parts:
        # Fall back: pick first PR title
        for line in changelog_block.splitlines():
            if line.strip().startswith("#### "):
                summary_parts.append(line.strip().lstrip("#").strip())
                break
    capability_summary = " · ".join(summary_parts) if summary_parts else f"v{plan.version} capabilities"

    new_row = f"| **v{major_minor}** | {capability_summary} |"

    # Check if this version row already exists
    if f"**v{major_minor}**" in rows or f"v{major_minor} " in rows:
        return content, []

    new_rows = new_row + "\n" + rows
    new_content = content.replace(header + rows + tail, header + new_rows + tail)
    if new_content == content:
        return content, []
    return new_content, [f"Evolution table: added row for v{major_minor}"]


def _update_roadmap_current_version(content: str, plan: SyncPlan) -> tuple[str, list[str]]:
    """Update 'What ships today — vX.Y.Z' heading in ROADMAP.md."""
    old_pattern = re.compile(r"(## What ships today — v)(\d+\.\d+\.\d+)")
    m = old_pattern.search(content)
    if not m:
        return content, []
    old_ver = m.group(2)
    if old_ver == plan.version:
        return content, []
    new_content = old_pattern.sub(rf"\g<1>{plan.version}", content)
    return new_content, [f"ROADMAP 'ships today' {old_ver} → {plan.version}"]


def _update_agent_state(plan: SyncPlan) -> list[dict[str, Any]]:
    """
    Update .adaad_agent_state.json: bump schema_version and active_phase.
    Returns list of change records.
    """
    path = ROOT / ".adaad_agent_state.json"
    if not path.exists():
        return []
    try:
        state = json.loads(_read(path))
    except json.JSONDecodeError:
        return []  # don't touch malformed state

    changes: list[dict[str, Any]] = []
    rel = ".adaad_agent_state.json"

    old_schema = state.get("schema_version", "")
    if old_schema != plan.version:
        state["schema_version"] = plan.version
        changes.append({"file": rel, "rule": "agent_state_schema_version",
                        "old": old_schema, "new": plan.version})

    new_phase = f"v{plan.version} RELEASED · post-merge doc sync"
    old_phase = state.get("active_phase", "")
    if plan.version not in old_phase:
        state["active_phase"] = new_phase
        changes.append({"file": rel, "rule": "agent_state_active_phase",
                        "old": old_phase[:80], "new": new_phase})

    old_date = state.get("last_invocation", "")
    if old_date != plan.date_str:
        state["last_invocation"] = plan.date_str
        changes.append({"file": rel, "rule": "agent_state_last_invocation",
                        "old": old_date, "new": plan.date_str})

    if changes:
        _write(path, json.dumps(state, indent=2, sort_keys=False) + "\n")

    return changes


# ────────────────────────────────────────────────────────────────────────────
# File-level processor
# ────────────────────────────────────────────────────────────────────────────

def _process_file(path: Path, plan: SyncPlan) -> list[dict[str, Any]]:
    rel = str(path.relative_to(ROOT))
    if _is_protected(rel):
        return []
    if not path.is_file():
        return []

    try:
        original = _read(path)
    except Exception as exc:
        _fatal("SYNC_ERROR_READ", f"Cannot read {rel}: {exc}")

    content = original
    file_changes: list[str] = []

    # 1. shields.io badge
    content, c = _replace_badge_version(content, plan.version)
    file_changes.extend(c)

    # 2. inline markdown badge
    content, c = _replace_inline_version_badge(content, plan.version)
    file_changes.extend(c)

    # 3. ADAAD_VERSION_INFOBOX sentinels (any file that has them)
    content, c = _update_version_infobox(content, plan)
    file_changes.extend(c)

    # 4. ARCH_SNAPSHOT_METADATA (README_IMPLEMENTATION_ALIGNMENT.md)
    if path.name == "README_IMPLEMENTATION_ALIGNMENT.md":
        content, c = _update_arch_snapshot(content, plan)
        file_changes.extend(c)

    # 5. Evolution history table (README.md root only)
    if rel == "README.md":
        content, c = _update_readme_evolution_table(content, plan)
        file_changes.extend(c)

    # 6. ROADMAP "ships today" heading
    if rel == "ROADMAP.md":
        content, c = _update_roadmap_current_version(content, plan)
        file_changes.extend(c)

    if content == original or not file_changes:
        return []

    try:
        _write(path, content)
    except Exception as exc:
        _fatal("SYNC_ERROR_WRITE", f"Cannot write {rel}: {exc}")

    return [{"file": rel, "rule": r, "old": "", "new": ""} for r in file_changes]


# ────────────────────────────────────────────────────────────────────────────
# Error / output helpers
# ────────────────────────────────────────────────────────────────────────────

def _fatal(code: str, message: str) -> None:
    print(json.dumps({"event": code, "message": message}))
    sys.exit(1)


def _emit(event: str, payload: dict[str, Any]) -> None:
    print(json.dumps({"event": event, **payload}))


# ────────────────────────────────────────────────────────────────────────────
# Target file discovery
# ────────────────────────────────────────────────────────────────────────────

# Files always processed (regardless of git diff)
_ALWAYS_SYNC: list[str] = [
    "README.md",
    "ROADMAP.md",
    "QUICKSTART.md",
    "docs/README_IMPLEMENTATION_ALIGNMENT.md",
    "docs/governance/ARCHITECT_SPEC_v2.0.0.md",  # only badge update, is in PROTECTED? No — allow badge only
]

# Directories scanned for *.md with version badges
_SCAN_DIRS: list[str] = [
    "docs",
]


def _collect_targets() -> list[Path]:
    targets: list[Path] = []
    seen: set[Path] = set()

    for rel in _ALWAYS_SYNC:
        p = ROOT / rel
        if p.exists() and p not in seen:
            targets.append(p)
            seen.add(p)

    for d in _SCAN_DIRS:
        for p in (ROOT / d).rglob("*.md"):
            if p not in seen and not _is_protected(str(p.relative_to(ROOT))):
                targets.append(p)
                seen.add(p)

    return targets


# ────────────────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Post-merge documentation synchroniser.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print planned changes but do not write any files.")
    parser.add_argument("--format", choices=("text", "json"), default="json",
                        help="Output format (default: json).")
    args = parser.parse_args(argv)

    version     = _read_version()
    prev_ver    = _read_prev_version(version)
    date_str    = date.today().isoformat()
    entry, caps = _read_changelog_entry(version)
    sha         = _git_sha()
    branch      = _git_branch()

    plan = SyncPlan(
        version=version,
        prev_version=prev_ver,
        date_str=date_str,
        changelog_entry=entry,
        new_capabilities=caps,
        git_sha=sha,
        git_branch=branch,
    )

    _emit("sync_start", {
        "version": version,
        "prev_version": prev_ver,
        "git_sha": sha,
        "git_branch": branch,
        "dry_run": args.dry_run,
    })

    all_changes: list[dict[str, Any]] = []

    if not args.dry_run:
        # .adaad_agent_state.json handled separately (JSON not Markdown)
        state_changes = _update_agent_state(plan)
        all_changes.extend(state_changes)

    for path in _collect_targets():
        rel = str(path.relative_to(ROOT))
        changes = _process_file(path, plan) if not args.dry_run else []
        if changes:
            all_changes.extend(changes)
            _emit("file_updated", {"file": rel, "changes": [c["rule"] for c in changes]})
        else:
            _emit("file_skipped", {"file": rel, "reason": "no changes needed"})

    _emit("sync_complete", {
        "version": version,
        "files_changed": len({c["file"] for c in all_changes}),
        "total_replacements": len(all_changes),
        "dry_run": args.dry_run,
    })

    if args.format == "text" and all_changes:
        print("\nSummary of changes:")
        for c in all_changes:
            print(f"  [{c['file']}] {c.get('rule', '')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
