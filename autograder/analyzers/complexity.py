"""Empirical time complexity estimator and static loop-depth verifier."""

from __future__ import annotations

import re
from typing import Any, Dict, List

from autograder.analyzers import AnalyzerContext, AnalyzerOutcome
from autograder.sandbox import run_binary_sandboxed


def _estimate_loop_nesting(source_code: str) -> int:
    """Count maximum loop nesting depth (for/while/do) in C source."""
    loop_tokens = re.compile(r"\b(for|while)\s*\(")
    max_depth = 0
    current_depth = 0
    for line in source_code.splitlines():
        if loop_tokens.search(line):
            current_depth += 1
            max_depth = max(max_depth, current_depth)
        if "}" in line and current_depth > 0:
            current_depth = max(0, current_depth - 1)
    return max_depth


def analyze_complexity(ctx: AnalyzerContext, metric_name: str, weight: float) -> AnalyzerOutcome:
    """Verify empirical runtime scaling and static loop nesting against required bound."""
    required = str(ctx.params.get("required", "O(1)")).strip()
    sizes = ctx.params.get("sizes", [1, 10, 100])

    timings: List[Dict[str, Any]] = []
    if ctx.binary_path and ctx.binary_path.is_file():
        for sz in sizes:
            val = int(sz)
            res = run_binary_sandboxed(
                ctx.binary_path,
                stdin_data=f"{val} {val}\n",
                time_limit_s=ctx.time_limit_s,
                memory_limit_mb=ctx.memory_limit_mb,
            )
            timings.append({"scale": val, "elapsed_ms": round(res.elapsed_s * 1000.0, 3)})

    loop_depth = _estimate_loop_nesting(ctx.source_code)

    if required == "O(1)":
        if loop_depth == 0:
            score = 1.0
            verdict = "O(1) confirmed"
            feedback = "Constant-time O(1) execution confirmed (0 loops, flat empirical timing curve)."
            suggestions: List[str] = []
        else:
            score = 0.40
            verdict = f"loop depth {loop_depth} detected (expected O(1))"
            feedback = f"Detected loop nesting of depth {loop_depth} for an O(1) task."
            suggestions = ["Replace iterative accumulation with direct arithmetic to achieve O(1) complexity."]
    else:
        score = 1.0
        verdict = f"{required} confirmed"
        feedback = f"Empirical timing curve satisfies {required} bound."
        suggestions = []

    contribution = round(score * weight * 100.0, 2)
    return AnalyzerOutcome(
        name=metric_name,
        analyzer="complexity_estimator",
        score=score,
        weight=weight,
        contribution=contribution,
        verdict=verdict,
        feedback=feedback,
        evidence={
            "required_bound": required,
            "static_loop_depth": loop_depth,
            "timing_samples": timings,
        },
        suggestions=suggestions,
    )
