# SPDX-License-Identifier: Apache-2.0
"""Compatibility shim for lineage v2 helpers.

Deprecated: import from ``runtime.evolution.lineage_v2``.
"""

from runtime.evolution.lineage_v2 import LINEAGE_V2_PATH, LineageResolutionError, resolve_chain

__all__ = ["LineageResolutionError", "LINEAGE_V2_PATH", "resolve_chain"]
