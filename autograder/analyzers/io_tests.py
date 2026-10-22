"""Hidden I/O test runner and failing counterexample extractor."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from autograder.analyzers import AnalyzerContext, AnalyzerOutcome
from autograder.sandbox import run_binary_sandboxed


DEFAULT_ADD_TESTS = [
    ("01_basic", "7 5\n", "12", "basic positive integers"),
    ("02_zeros", "0 0\n", "0", "both operands zero"),
    ("03_negatives", "-15 -25\n", "-40", "two negative integers"),
    ("04_mixed_sign", "-42 100\n", "58", "negative plus positive"),
    ("05_identity", "999999 0\n", "999999", "additive identity"),
    ("06_large_safe", "1000000000 1000000000\n", "2000000000", "large 32-bit safe sum"),
    ("07_int_max_overflow", "2147483647 1\n", "2147483648", "INT_MAX + 1 signed 32-bit overflow"),
    ("08_int_min_underflow", "-2147483648 -1\n", "-2147483649", "INT_MIN - 1 signed 32-bit underflow"),
    ("09_extra_whitespace", "   14     28  \n", "42", "leading and multiple internal spaces"),
    ("10_opposite_cancel", "123456789 -123456789\n", "0", "exact additive inverse cancellation"),
]


def _load_test_cases(testset_dir: Path) -> List[tuple[str, str, str, str]]:
    """Load .in/.out pairs from disk, falling back to the built-in 10-test suite."""
    if testset_dir.is_dir():
        in_files = sorted(testset_dir.glob("*.in"))
        cases: List[tuple[str, str, str, str]] = []
        for in_file in in_files:
            out_file = in_file.with_suffix(".out")
            note_file = in_file.with_suffix(".note")
            if out_file.is_file():
                inp = in_file.read_text(encoding="utf-8")
                exp = out_file.read_text(encoding="utf-8").strip()
                note = note_file.read_text(encoding="utf-8").strip() if note_file.is_file() else in_file.stem
                cases.append((in_file.stem, inp, exp, note))
        if cases:
            return cases
    return list(DEFAULT_ADD_TESTS)


def analyze_io_tests(ctx: AnalyzerContext, metric_name: str, weight: float) -> AnalyzerOutcome:
    """Run the compiled binary against the hidden test suite and record counterexamples."""
    if ctx.binary_path is None or not ctx.binary_path.is_file():
        return AnalyzerOutcome(
            name=metric_name,
            analyzer="io_tests",
            score=0.0,
            weight=weight,
            contribution=0.0,
            verdict="binary unavailable",
            feedback="Submission did not compile; 0 tests executed.",
            evidence={"tests_passed": 0, "tests_total": 0, "failing": []},
        )

    rel_dir = str(ctx.params.get("testset_dir", "tests/add/"))
    testset_dir = (ctx.workspace_root / rel_dir).resolve()
    cases = _load_test_cases(testset_dir)

    passed = 0
    failing: List[Dict[str, Any]] = []

    for test_id, inp, expected, description in cases:
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
            note = description
            if res.timed_out:
                note = f"timed out after {ctx.time_limit_s}s ({description})"
            elif "overflow" in description and got in ("-2147483648", "2147483647"):
                note = "runtime error: signed 32-bit integer overflow wrapped around"
            failing.append(
                {
                    "test_id": test_id,
                    "input": inp.strip(),
                    "expected": expected,
                    "got": got,
                    "note": note,
                    "why": (
                        "a + b overflows on 32-bit signed ints. Use long long or check that "
                        "b <= INT_MAX - a before adding."
                        if "overflow" in description or "underflow" in description
                        else f"Output '{got}' did not match expected '{expected}' ({description})."
                    ),
                }
            )

    total = len(cases)
    score = round(passed / total, 4) if total else 0.0
    contribution = round(score * weight * 100.0, 2)
    verdict = f"{passed} of {total} tests pass"

    if failing:
        first_fail = failing[0]
        feedback = (
            f"{passed}/{total} tests pass. Fails on input '{first_fail['input']}' "
            f"(expected {first_fail['expected']}, got {first_fail['got']}): {first_fail['note']}."
        )
        suggestions = ["Handle 64-bit integer range explicitly using `long long` and `%lld`."]
    else:
        feedback = f"All {total}/{total} hidden I/O tests passed."
        suggestions = []

    return AnalyzerOutcome(
        name=metric_name,
        analyzer="io_tests",
        score=score,
        weight=weight,
        contribution=contribution,
        verdict=verdict,
        feedback=feedback,
        evidence={
            "tests_passed": passed,
            "tests_total": total,
            "failing": failing,
        },
        suggestions=suggestions,
    )
