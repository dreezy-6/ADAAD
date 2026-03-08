#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_SNIPPETS = {
    "README.md": [
        "Governance & Determinism Guarantees (Current State)",
        "ADAAD_DISPATCH_LATENCY_BUDGET_MS",
        "ADAAD_DETERMINISTIC_LOCK",
    ],
    "runtime/README.md": [
        "Deterministic Guarantees",
    ],
    "ui/README.md": [
        "Aponi URL is derived from runtime constants",
    ],
    "docs/releases/RELEASE_AUDIT_CHECKLIST.md": [
        "Replay on two independent environments",
        "Constitution checksum verified",
    ],
    "docs/DOCS_VISUAL_STYLE_GUIDE.md": [
        "Approved badge style",
        "Alt-text requirements",
    ],
    "docs/assets/IMAGE_PROVENANCE.md": [
        "adaad-banner.svg",
    ],
}

CANONICAL_TRIGGER_VARIABLE = "ADAAD_ROADMAP_AMENDMENT_TRIGGER_INTERVAL"
LEGACY_TRIGGER_VARIABLE = "ADAAD_AMENDMENT_TRIGGER_INTERVAL"
LEGACY_TRIGGER_ALLOWLIST = {
    "CHANGELOG.md",
    "docs/ENVIRONMENT_VARIABLES.md",
}
COMPATIBILITY_NOTE_SNIPPET = "Compatibility note:"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate strict README and release-doc snippet alignment.")
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="json",
        help="Output format. Defaults to json for CI readability.",
    )
    return parser


def _emit(missing: list[str], output_format: str) -> None:
    if output_format == "json":
        payload = {
            "validator": "readme_alignment",
            "ok": not missing,
            "missing": sorted(missing),
        }
        print(json.dumps(payload, sort_keys=True))
        return

    if missing:
        for item in sorted(missing):
            print(item)
        return
    print("readme_alignment_ok")


def _iter_markdown_files() -> list[Path]:
    markdown_files = [
        path
        for path in ROOT.rglob("*.md")
        if ".git" not in path.parts and "node_modules" not in path.parts
    ]
    return sorted(markdown_files)


def main() -> int:
    args = _build_parser().parse_args()
    missing: list[str] = []
    try:
        for rel, snippets in sorted(REQUIRED_SNIPPETS.items()):
            path = ROOT / rel
            if not path.exists():
                missing.append(f"missing_file:{rel}")
                continue
            text = path.read_text(encoding="utf-8")
            for snippet in snippets:
                if snippet not in text:
                    missing.append(f"missing_snippet:{rel}:{snippet}")

        for path in _iter_markdown_files():
            rel = path.relative_to(ROOT).as_posix()
            text = path.read_text(encoding="utf-8")
            has_canonical = CANONICAL_TRIGGER_VARIABLE in text
            has_legacy = LEGACY_TRIGGER_VARIABLE in text
            if has_canonical and has_legacy and rel not in LEGACY_TRIGGER_ALLOWLIST:
                missing.append(f"mixed_env_var_naming:{rel}")
            if has_legacy and rel not in LEGACY_TRIGGER_ALLOWLIST:
                missing.append(f"legacy_env_var_reference:{rel}:{LEGACY_TRIGGER_VARIABLE}")
            if has_legacy and rel in LEGACY_TRIGGER_ALLOWLIST and COMPATIBILITY_NOTE_SNIPPET not in text and rel != "CHANGELOG.md":
                missing.append(f"missing_compatibility_note:{rel}")
    except Exception as exc:  # fail closed
        missing.append(f"validator_error:{exc.__class__.__name__}:{exc}")

    _emit(missing=missing, output_format=args.format)
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
