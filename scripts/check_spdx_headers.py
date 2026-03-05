#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Enforce SPDX-License-Identifier headers on all Python source files.

Usage:
    python scripts/check_spdx_headers.py [--fix] [paths...]

Exits non-zero if any file is missing a valid SPDX header.
With --fix, writes the header to offending files.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

SPDX_LINE = "# SPDX-License-Identifier: Apache-2.0"

EXCLUDE_PATTERNS = (
    ".git",
    "__pycache__",
    "*.egg-info",
    "node_modules",
    ".venv",
    "venv",
    "archives/",
    "brand/",
)

DEFAULT_SCAN_DIRS = (
    "app",
    "adaad",
    "runtime",
    "scripts",
    "security",
    "tests",
    "tools",
    "governance",
    "ui",
)


def _excluded(path: Path) -> bool:
    parts = path.parts
    return any(excl.rstrip("/") in parts or path.match(excl) for excl in EXCLUDE_PATTERNS)


def _has_spdx(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh):
                if i > 5:
                    break
                if "SPDX-License-Identifier" in line:
                    return True
    except OSError:
        pass
    return False


def _fix_file(path: Path) -> None:
    content = path.read_text(encoding="utf-8")
    path.write_text(SPDX_LINE + "\n" + content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check SPDX headers on Python files.")
    parser.add_argument("paths", nargs="*", help="Paths to scan (default: repo source dirs)")
    parser.add_argument("--fix", action="store_true", help="Add missing headers automatically")
    args = parser.parse_args()

    scan_roots = [REPO_ROOT / p for p in (args.paths or DEFAULT_SCAN_DIRS)]
    violations: list[Path] = []

    for root in scan_roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            if _excluded(path):
                continue
            if not _has_spdx(path):
                violations.append(path)

    if not violations:
        print(f"✅ SPDX check passed — all Python files have license headers.")
        return 0

    for v in violations:
        rel = v.relative_to(REPO_ROOT)
        if args.fix:
            _fix_file(v)
            print(f"  fixed: {rel}")
        else:
            print(f"  MISSING: {rel}")

    if args.fix:
        print(f"✅ Fixed {len(violations)} file(s).")
        return 0

    print(f"\n❌ {len(violations)} file(s) missing SPDX-License-Identifier header.")
    print("Run with --fix to add headers automatically.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
