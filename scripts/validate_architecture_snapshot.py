#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Validate architecture snapshot metadata against canonical version + git metadata.

By default this script validates tracked snapshot docs are up-to-date.
Use --write to refresh the managed metadata block.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.report_version import build_snapshot_metadata

SNAPSHOT_DOC = ROOT / "docs" / "README_IMPLEMENTATION_ALIGNMENT.md"
START = "<!-- ARCH_SNAPSHOT_METADATA:START -->"
END = "<!-- ARCH_SNAPSHOT_METADATA:END -->"


def _metadata_block() -> str:
    meta = build_snapshot_metadata()
    return "\n".join(
        [
            START,
            "## Architecture Deep-Dive Snapshot",
            "",
            "| Metric | Value |",
            "| --- | --- |",
            f"| Report version | `{meta['report_version']}` |",
            f"| Branch | `{meta['branch']}` |",
            f"| Tag | `{meta['tag']}` |",
            f"| Short SHA | `{meta['short_sha']}` |",
            "",
            "All future architecture snapshots MUST include branch, tag (if any), and short SHA.",
            END,
        ]
    )


def _replace_managed_block(content: str, new_block: str) -> str:
    if START not in content or END not in content:
        raise ValueError("managed metadata block markers not found")
    head, rest = content.split(START, 1)
    _old, tail = rest.split(END, 1)
    return f"{head}{new_block}{tail}"


def _extract_row_value(block: str, metric: str) -> str:
    pattern = rf"^\|\s*{re.escape(metric)}\s*\|\s*`([^`]+)`\s*\|$"
    for line in block.splitlines():
        match = re.match(pattern, line.strip())
        if match:
            return match.group(1).strip()
    return ""


def _validate_managed_block(content: str) -> tuple[bool, str]:
    if START not in content or END not in content:
        return False, "managed metadata block markers not found"

    _head, rest = content.split(START, 1)
    existing_block, _tail = rest.split(END, 1)
    existing = existing_block.strip()
    expected_report_version = build_snapshot_metadata()["report_version"]
    report_version = _extract_row_value(existing, "Report version")
    branch = _extract_row_value(existing, "Branch")
    tag = _extract_row_value(existing, "Tag")
    short_sha = _extract_row_value(existing, "Short SHA")

    if report_version != expected_report_version:
        return False, "report version drift detected"
    if not branch:
        return False, "branch metadata missing"
    if not tag:
        return False, "tag metadata missing"
    if not re.fullmatch(r"[0-9a-f]{7,12}|unknown", short_sha):
        return False, "short SHA metadata invalid"

    return True, "architecture snapshot metadata OK"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate architecture snapshot metadata block.")
    parser.add_argument("--write", action="store_true", help="Rewrite managed metadata block in-place")
    args = parser.parse_args()

    content = SNAPSHOT_DOC.read_text(encoding="utf-8")
    if args.write:
        block = _metadata_block()
        updated = _replace_managed_block(content, block)
        SNAPSHOT_DOC.write_text(updated, encoding="utf-8")
        print(f"updated {SNAPSHOT_DOC.relative_to(ROOT)}")
        return 0

    is_valid, message = _validate_managed_block(content)
    if not is_valid:
        print(f"architecture snapshot metadata drift detected: {message}", file=sys.stderr)
        print("run: python scripts/validate_architecture_snapshot.py --write", file=sys.stderr)
        return 1

    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
