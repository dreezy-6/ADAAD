# SPDX-License-Identifier: Apache-2.0
"""Deterministic writer for promotion evidence bundles."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from runtime import ROOT_DIR
from runtime.governance.foundation import canonical_json, sha256_prefixed_digest

PROMOTION_MANIFESTS_DIR = ROOT_DIR / "security" / "promotion_manifests"


def write_promotion_evidence_bundle(
    *,
    mutation_id: str,
    bundle: Mapping[str, Any],
    output_dir: Path | None = None,
) -> Path:
    target_dir = Path(output_dir) if output_dir is not None else PROMOTION_MANIFESTS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    material = dict(bundle)
    material["bundle_hash"] = sha256_prefixed_digest(canonical_json(material))
    output_path = target_dir / f"{mutation_id}_evidence.json"
    output_path.write_text(json.dumps(material, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path
