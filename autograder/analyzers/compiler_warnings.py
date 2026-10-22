"""Compiler warning & syntax hygiene analyzer."""

from __future__ import annotations

import os
import re
from typing import List

from autograder.analyzers import AnalyzerContext, AnalyzerOutcome
from autograder.sandbox import compile_submission


def analyze_compiler_warnings(ctx: AnalyzerContext, metric_name: str, weight: float) -> AnalyzerOutcome:
    """Compile with strict warning flags and score based on diagnostic count."""
    raw_flags = str(ctx.params.get("flags", "-Wall -Wextra -std=c11"))
    # Strip -Werror during diagnostic collection so we count warnings rather than hard-aborting
    flag_list = [f for f in raw_flags.split() if f != "-Werror"]
    res = compile_submission(ctx.source_path, flags=flag_list)
    if res.binary_path and res.binary_path.is_file():
        try:
            os.remove(res.binary_path)
        except OSError:
            pass

    warnings: List[str] = list(res.warnings)

    # Also check whether scanf return value is ignored (common C pitfall that some clang builds omit unless _FORTIFY_SOURCE)
    if re.search(r"(?<!=\s)(?<!=\s\()(?<!if\s\()\bscanf\s*\(", ctx.source_code) and not re.search(
        r"(if|while|=)\s*\(?\s*scanf\s*\(", ctx.source_code
    ):
        warnings.append("warning: ignoring return value of 'scanf' [-Wunused-result]")

    if not res.compiled and res.errors:
        return AnalyzerOutcome(
            name=metric_name,
            analyzer="compiler_warnings",
            score=0.0,
            weight=weight,
            contribution=0.0,
            verdict=f"{len(res.errors)} compile error(s)",
            feedback="Compilation failed under strict C11 flags.",
            evidence={"warnings": warnings, "errors": res.errors, "flags": raw_flags},
            suggestions=["Fix syntax and type errors reported by the compiler."],
        )

    # Deduct 0.10 per warning, floor at 0.0
    penalty = 0.10 * len(warnings)
    score = round(max(0.0, 1.0 - penalty), 4)
    contribution = round(score * weight * 100.0, 2)

    if warnings:
        tag_match = re.search(r"(\[-W[^\]]+\])", warnings[0])
        tag = tag_match.group(1).strip("[]") if tag_match else "compiler warning"
        verdict = f"{tag} x{len(warnings)}"
        feedback = f"{len(warnings)} compiler warning(s) emitted ({tag})."
        suggestions = ["Check the return value of `scanf` and resolve all `-Wall -Wextra` warnings."]
    else:
        verdict = "0 warnings"
        feedback = "Clean compilation under strict C11 flags."
        suggestions = []

    return AnalyzerOutcome(
        name=metric_name,
        analyzer="compiler_warnings",
        score=score,
        weight=weight,
        contribution=contribution,
        verdict=verdict,
        feedback=feedback,
        evidence={"warnings_count": len(warnings), "warnings": warnings, "flags": raw_flags},
        suggestions=suggestions,
    )
