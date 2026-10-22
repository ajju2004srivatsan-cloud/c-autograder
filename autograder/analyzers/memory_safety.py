"""AddressSanitizer (ASan) and UndefinedBehaviorSanitizer (UBSan) memory safety analyzer."""

from __future__ import annotations

import os
from typing import List

from autograder.analyzers import AnalyzerContext, AnalyzerOutcome
from autograder.sandbox import compile_submission, run_binary_sandboxed


def analyze_sanitizer_run(ctx: AnalyzerContext, metric_name: str, weight: float) -> AnalyzerOutcome:
    """Compile with -fsanitize=address,undefined and execute standard workloads."""
    raw_flags = str(ctx.params.get("flags", "-fsanitize=address,undefined"))
    compile_flags = ["-O1", "-g", *raw_flags.split(), "-std=c11"]

    san_compile = compile_submission(ctx.source_path, flags=compile_flags)
    if not san_compile.compiled or san_compile.binary_path is None:
        return AnalyzerOutcome(
            name=metric_name,
            analyzer="sanitizer_run",
            score=0.0,
            weight=weight,
            contribution=0.0,
            verdict="sanitizer build failed",
            feedback="Failed to compile submission with ASan/UBSan instrumentation.",
            evidence={"flags": raw_flags, "errors": san_compile.errors},
        )

    diagnostics: List[str] = []
    try:
        for sample_in in ("7 5\n", "0 0\n", "-42 100\n"):
            res = run_binary_sandboxed(
                san_compile.binary_path,
                stdin_data=sample_in,
                time_limit_s=max(2.0, ctx.time_limit_s),
                memory_limit_mb=0,  # ASan reserves large virtual shadow memory
                env_overrides={"ASAN_OPTIONS": "detect_leaks=0:abort_on_error=0"},
            )
            if "ERROR: AddressSanitizer" in res.stderr or "runtime error:" in res.stderr:
                for line in res.stderr.splitlines():
                    if "ERROR:" in line or "runtime error:" in line or "SUMMARY:" in line:
                        diagnostics.append(line.strip())
    finally:
        if san_compile.binary_path and san_compile.binary_path.is_file():
            try:
                os.remove(san_compile.binary_path)
            except OSError:
                pass

    if diagnostics:
        score = 0.20
        verdict = f"{len(diagnostics)} sanitizer diagnostic(s)"
        feedback = f"ASan/UBSan flagged issues: {diagnostics[0]}"
        suggestions = ["Fix memory corruption or undefined behavior flagged by ASan/UBSan."]
    else:
        score = 1.0
        verdict = "ASan/UBSan clean"
        feedback = "No memory corruption, out-of-bounds access, or undefined behavior on standard runs."
        suggestions = []

    contribution = round(score * weight * 100.0, 2)
    return AnalyzerOutcome(
        name=metric_name,
        analyzer="sanitizer_run",
        score=score,
        weight=weight,
        contribution=contribution,
        verdict=verdict,
        feedback=feedback,
        evidence={"flags": raw_flags, "diagnostics": diagnostics},
        suggestions=suggestions,
    )
