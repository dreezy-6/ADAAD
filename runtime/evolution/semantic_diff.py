# SPDX-License-Identifier: Apache-2.0
"""
SemanticDiffEngine — Phase 4 AST-based mutation risk and complexity scorer.

Purpose:
    Replaces LOC-count heuristics in compute_diff_penalty and compute_risk_penalty
    with parse-tree analysis. When source code is available, risk and complexity
    signals are derived from structural deltas (AST depth, cyclomatic complexity,
    import surface) rather than raw line counts.

Scoring formula (from ROADMAP.md Phase 4 spec):
    risk_score = (ast_depth_delta × 0.3) + (cyclomatic_delta × 0.4)
               + (import_surface_delta × 0.3)
    All components clamped to [0.0, 1.0] before weighting.
    Final risk_score clamped to [0.0, 1.0].

    complexity_score = (node_count_norm × 0.5) + (nesting_depth_norm × 0.5)
    All components clamped to [0.0, 1.0] before weighting.

Determinism contract:
    - All AST traversal uses ast.walk() — deterministic traversal order.
    - All arithmetic is pure float on deterministic inputs.
    - Falls back to LOC-based scores when source is unavailable or
      unparseable — identical to v1 scoring (no regression).
    - ALGORITHM_VERSION baked in for replay verification.

Constitutional invariants:
    - SemanticDiffEngine is advisory. It produces float scores [0.0, 1.0].
    - Callers pass scores into ScoringWeights via standard channels.
    - GovernanceGate never referenced here.
    - Graceful fallback on any parse error: returns LOC-based estimate.

Normalization:
    AST depth:        normalized against MAX_AST_DEPTH = 50
    Cyclomatic:       normalized against MAX_CYCLOMATIC = 30
    Import surface:   normalized against MAX_IMPORTS = 20
    Node count:       normalized against MAX_NODES = 500
    Nesting depth:    normalized against MAX_NESTING = 15
"""

from __future__ import annotations

import ast
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

ALGORITHM_VERSION: str = "semantic_diff_v1.0"

# --- Normalization caps -------------------------------------------------------
MAX_AST_DEPTH:   int = 50
MAX_CYCLOMATIC:  int = 30
MAX_IMPORTS:     int = 20
MAX_NODES:       int = 500
MAX_NESTING:     int = 15

# --- Risk formula weights (from ROADMAP Phase 4 spec) -------------------------
W_AST_DEPTH:    float = 0.30
W_CYCLOMATIC:   float = 0.40
W_IMPORT_SURF:  float = 0.30

# --- Complexity formula weights -----------------------------------------------
W_NODE_COUNT:   float = 0.50
W_NESTING_DEPTH: float = 0.50


# --- AST Analysis dataclass ---------------------------------------------------

@dataclass
class ASTMetrics:
    """Structural metrics extracted from a single Python source file."""
    node_count:      int   = 0
    max_depth:       int   = 0
    cyclomatic:      int   = 0    # branches + 1
    import_count:    int   = 0
    function_count:  int   = 0
    class_count:     int   = 0
    max_nesting:     int   = 0    # deepest nested block

    @classmethod
    def from_source(cls, source: str) -> "ASTMetrics":
        """
        Parse source and extract structural metrics.
        Raises SyntaxError on unparseable input — callers must handle.
        """
        tree = ast.parse(source)
        m = cls()
        m.node_count = sum(1 for _ in ast.walk(tree))
        m.max_depth = _max_ast_depth(tree)
        m.cyclomatic = _cyclomatic_complexity(tree)
        m.import_count = sum(
            1 for n in ast.walk(tree)
            if isinstance(n, (ast.Import, ast.ImportFrom))
        )
        m.function_count = sum(
            1 for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        )
        m.class_count = sum(1 for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
        m.max_nesting = _max_nesting_depth(tree)
        return m


@dataclass
class SemanticDiff:
    """
    Structural delta between a before and after AST snapshot.

    risk_score:       [0.0, 1.0] — structural risk of the mutation.
    complexity_score: [0.0, 1.0] — structural complexity of the mutation.
    algorithm_version: version string for replay verification.
    fallback_used:    True when source was unavailable — LOC-based estimate.
    """
    risk_score:        float
    complexity_score:  float
    algorithm_version: str    = ALGORITHM_VERSION
    fallback_used:     bool   = False
    before:            Optional[ASTMetrics] = None
    after:             Optional[ASTMetrics] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk_score":        round(self.risk_score, 4),
            "complexity_score":  round(self.complexity_score, 4),
            "algorithm_version": self.algorithm_version,
            "fallback_used":     self.fallback_used,
        }


# --- SemanticDiffEngine -------------------------------------------------------

class SemanticDiffEngine:
    """
    Computes risk_score and complexity_score from AST deltas.

    Usage:
        engine = SemanticDiffEngine()
        diff = engine.diff(before_source="...", after_source="...")
        risk = diff.risk_score
        complexity = diff.complexity_score

    For code_diff-only inputs (no source available):
        diff = engine.diff_from_code_diff(code_diff_dict)
    """

    def diff(
        self,
        before_source: Optional[str] = None,
        after_source:  Optional[str] = None,
    ) -> SemanticDiff:
        """
        Compute semantic diff from Python source strings.

        Falls back to complexity_score=0.5, risk_score=0.5 when either
        source is None or unparseable.
        """
        if before_source is None or after_source is None:
            return SemanticDiff(risk_score=0.5, complexity_score=0.5, fallback_used=True)

        try:
            before = ASTMetrics.from_source(before_source)
            after  = ASTMetrics.from_source(after_source)
        except SyntaxError:
            return SemanticDiff(risk_score=0.5, complexity_score=0.5, fallback_used=True)

        risk_score       = _compute_risk_score(before, after)
        complexity_score = _compute_complexity_score(after)

        return SemanticDiff(
            risk_score=risk_score,
            complexity_score=complexity_score,
            before=before,
            after=after,
        )

    def diff_from_code_diff(self, code_diff: Dict[str, Any]) -> SemanticDiff:
        """
        Derive semantic-equivalent scores from a code_diff dict when
        source AST is unavailable (LOC-based fallback with structured mapping).

        Produces deterministic results from code_diff field values.
        Preserves v1 score magnitudes while using semantic formula structure.
        """
        loc_added   = int(code_diff.get("loc_added",    0) or 0)
        loc_deleted = int(code_diff.get("loc_deleted",  0) or 0)
        files       = int(code_diff.get("files_touched", 0) or 0)
        risk_tags   = list(code_diff.get("risk_tags",   []) or [])

        # Approximate AST metrics from LOC
        total_loc   = max(loc_added + loc_deleted, 0)
        depth_proxy = _clamp01(total_loc / (MAX_AST_DEPTH * 10))
        cyclo_proxy = _clamp01(files / MAX_CYCLOMATIC)
        import_proxy = _clamp01(len(risk_tags) / MAX_IMPORTS)

        risk_score = (
            depth_proxy  * W_AST_DEPTH +
            cyclo_proxy  * W_CYCLOMATIC +
            import_proxy * W_IMPORT_SURF
        )

        node_proxy   = _clamp01(total_loc / MAX_NODES)
        nesting_proxy = _clamp01(files / MAX_NESTING)
        complexity_score = node_proxy * W_NODE_COUNT + nesting_proxy * W_NESTING_DEPTH

        return SemanticDiff(
            risk_score=_clamp01(risk_score),
            complexity_score=_clamp01(complexity_score),
            fallback_used=True,
        )


# --- AST traversal helpers ----------------------------------------------------

def _max_ast_depth(tree: ast.AST) -> int:
    """Recursively compute maximum depth of the AST."""
    def depth(node: ast.AST, current: int) -> int:
        children = list(ast.iter_child_nodes(node))
        if not children:
            return current
        return max(depth(child, current + 1) for child in children)
    return depth(tree, 0)


def _cyclomatic_complexity(tree: ast.AST) -> int:
    """McCabe cyclomatic complexity: count decision branches + 1."""
    branch_nodes = (
        ast.If, ast.While, ast.For, ast.AsyncFor,
        ast.ExceptHandler, ast.With, ast.AsyncWith,
        ast.Assert, ast.comprehension,
    )
    branches = sum(1 for n in ast.walk(tree) if isinstance(n, branch_nodes))
    # Boolean operators each add a branch
    bool_ops = sum(
        len(n.values) - 1
        for n in ast.walk(tree)
        if isinstance(n, ast.BoolOp)
    )
    return branches + bool_ops + 1


def _max_nesting_depth(tree: ast.AST) -> int:
    """Compute maximum nesting depth of block statements."""
    nesting_nodes = (ast.If, ast.While, ast.For, ast.AsyncFor,
                     ast.With, ast.AsyncWith, ast.Try, ast.FunctionDef,
                     ast.AsyncFunctionDef, ast.ClassDef)

    def nesting(node: ast.AST, current: int) -> int:
        if isinstance(node, nesting_nodes):
            current += 1
        children = list(ast.iter_child_nodes(node))
        if not children:
            return current
        return max(nesting(child, current) for child in children)

    return nesting(tree, 0)


# --- Score computation --------------------------------------------------------

def _compute_risk_score(before: ASTMetrics, after: ASTMetrics) -> float:
    """
    risk_score = (ast_depth_delta × 0.3) + (cyclomatic_delta × 0.4)
               + (import_surface_delta × 0.3)
    Deltas are absolute increases; decreases contribute zero.
    """
    depth_delta  = max(0, after.max_depth    - before.max_depth)
    cyclo_delta  = max(0, after.cyclomatic   - before.cyclomatic)
    import_delta = max(0, after.import_count - before.import_count)

    depth_norm  = _clamp01(depth_delta  / MAX_AST_DEPTH)
    cyclo_norm  = _clamp01(cyclo_delta  / MAX_CYCLOMATIC)
    import_norm = _clamp01(import_delta / MAX_IMPORTS)

    return round(_clamp01(
        depth_norm  * W_AST_DEPTH +
        cyclo_norm  * W_CYCLOMATIC +
        import_norm * W_IMPORT_SURF
    ), 4)


def _compute_complexity_score(after: ASTMetrics) -> float:
    """
    complexity_score = (node_count_norm × 0.5) + (nesting_depth_norm × 0.5)
    Absolute measure of after-state complexity.
    """
    node_norm    = _clamp01(after.node_count / MAX_NODES)
    nesting_norm = _clamp01(after.max_nesting / MAX_NESTING)
    return round(_clamp01(
        node_norm    * W_NODE_COUNT +
        nesting_norm * W_NESTING_DEPTH
    ), 4)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


# --- Integration helper -------------------------------------------------------

def enrich_code_diff_with_semantic(
    code_diff: Dict[str, Any],
    before_source: Optional[str] = None,
    after_source:  Optional[str] = None,
) -> Dict[str, Any]:
    """
    Augment a code_diff dict with semantic_risk_score and semantic_complexity_score.

    The enriched dict is backward-compatible: all original keys preserved.
    Callers may pass semantic scores to ScoringWeights risk_penalty /
    complexity_penalty channels.
    """
    engine = SemanticDiffEngine()
    if before_source is not None and after_source is not None:
        diff = engine.diff(before_source, after_source)
    else:
        diff = engine.diff_from_code_diff(code_diff)

    enriched = dict(code_diff)
    enriched["semantic_risk_score"]       = diff.risk_score
    enriched["semantic_complexity_score"] = diff.complexity_score
    enriched["semantic_algorithm"]        = diff.algorithm_version
    enriched["semantic_fallback_used"]    = diff.fallback_used
    return enriched


__all__ = [
    "SemanticDiffEngine",
    "SemanticDiff",
    "ASTMetrics",
    "enrich_code_diff_with_semantic",
    "ALGORITHM_VERSION",
]
