"""Targeted corner-case and boundary condition probe (negatives, zero, 32-bit overflow)."""

from __future__ import annotations

from typing import Any, Dict, List

from autograder.analyzers import AnalyzerContext, AnalyzerOutcome
from autograder.sandbox import run_binary_sandboxed


CORNER_PROBES: Dict[str, List[tuple[str, str, str]]] = {
    "negatives": [
        ("-100 -200\n", "-300", "sum of two negative numbers"),
        ("-1 1\n", "0", "negative and positive cancellation"),
    ],
    "zero": [
        ("0 0\n", "0", "zero plus zero"),
        ("0 -999\n", "-999", "zero plus negative"),
    ],
    "int_overflow": [
        ("2147483647 1\n", "2147483648", "INT_MAX + 1 overflow"),
    ],
}


def analyze_edge_cases(ctx: AnalyzerContext, metric_name: str, weight: float) -> AnalyzerOutcome:
    """Probe specific logical corner categories requested by the instructor rules."""
    if ctx.binary_path is None or not ctx.binary_path.is_file():
        return AnalyzerOutcome(
            name=metric_name,
            analyzer="edge_case_runner",
            score=0.0,
            weight=weight,
            contribution=0.0,
            verdict="binary unavailable",
            feedback="Binary could not be executed for logical edge-case checks.",
            evidence={"probed": [], "failures": []},
        )

    requested_cases = ctx.params.get("cases", ["negatives", "zero", "int_overflow"])
    probes: List[tuple[str, str, str, str]] = []
    for cat in requested_cases:
        for inp, exp, desc in CORNER_PROBES.get(str(cat), []):
            probes.append((str(cat), inp, exp, desc))

    if not probes:
        probes = [("default", "0 0\n", "0", "zero identity")]

    passed = 0
    failures: List[Dict[str, Any]] = []
    for category, inp, expected, desc in probes:
        res = run_binary_sandboxed(
            ctx.binary_path,
            stdin_data=inp,
            time_limit_s=ctx.time_limit_s,
            memory_limit_mb=ctx.memory_limit_mb,
        )
        got = res.stdout.strip()
        if not res.timed_out and not res.crashed and res.exit_code == 0 and got == expected:
            passed += 1
        else:
            failures.append(
                {
                    "category": category,
                    "input": inp.strip(),
                    "expected": expected,
                    "got": got,
                    "description": desc,
                }
            )

    total = len(probes)
    score = round(passed / total, 4)
    contribution = round(score * weight * 100.0, 2)

    if failures:
        first = failures[0]
        verdict = f"{first['description']} not handled"
        feedback = f"{passed}/{total} edge probes passed; {first['description']} failed (input '{first['input']}')."
        suggestions = ["Handle overflow explicitly with a wider integer type (`long long`)."]
    else:
        verdict = "all corner cases handled"
        feedback = f"All {total}/{total} logical corner cases passed."
        suggestions = []

    return AnalyzerOutcome(
        name=metric_name,
        analyzer="edge_case_runner",
        score=score,
        weight=weight,
        contribution=contribution,
        verdict=verdict,
        feedback=feedback,
        evidence={"probes_passed": passed, "probes_total": total, "failures": failures},
        suggestions=suggestions,
    )
