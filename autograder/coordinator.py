"""Coordinator engine: runs first pass, dispatches analyzers, and collates JSON + text reports."""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

from autograder.analyzers import AnalyzerContext, AnalyzerFunc, AnalyzerOutcome
from autograder.analyzers.compiler_warnings import analyze_compiler_warnings
from autograder.analyzers.complexity import analyze_complexity
from autograder.analyzers.edge_cases import analyze_edge_cases
from autograder.analyzers.io_tests import analyze_io_tests
from autograder.analyzers.memory_safety import analyze_sanitizer_run
from autograder.analyzers.readability_originality import (
    analyze_llm_review,
    analyze_similarity_flag,
)
from autograder.analyzers.static_structure import (
    analyze_function_split,
    analyze_static_analysis,
)
from autograder.rules import GradingRules, load_rules
from autograder.sandbox import get_compiler_version, run_first_pass


ANALYZER_REGISTRY: Dict[str, AnalyzerFunc] = {
    "io_tests": analyze_io_tests,
    "compiler_warnings": analyze_compiler_warnings,
    "static_analysis": analyze_static_analysis,
    "function_split": analyze_function_split,
    "edge_case_runner": analyze_edge_cases,
    "complexity_estimator": analyze_complexity,
    "sanitizer_run": analyze_sanitizer_run,
    "llm_review": analyze_llm_review,
    "similarity_flag": analyze_similarity_flag,
}

EXECUTION_ANALYZERS = {"io_tests", "edge_case_runner", "complexity_estimator", "sanitizer_run"}


USEFULNESS_AND_LIMITATIONS: Dict[str, List[Dict[str, str]]] = {
    "usefulness": [
        {
            "use_case": "Large-enrollment CS1/CS2 university programming courses",
            "example": (
                "An introductory C course with 450 students submits weekly lab assignments. "
                "The agent grades every upload in under 3 seconds with identical strictness on "
                "correctness, compiler hygiene, modularity, and ASan memory safety."
            ),
            "benefit": (
                "Eliminates grading variance across TAs and gives students immediate counterexamples."
            ),
        },
        {
            "use_case": "Coding-interview and embedded systems hiring screens",
            "example": (
                "A company runs 500 candidate submissions for an 'add two integers safely' task. "
                "The agent ranks them by correctness, edge-case handling and memory safety, and "
                "gives an explainable per-metric score."
            ),
            "benefit": (
                "Fast first-round filtering where every rejection can be justified metric by metric."
            ),
        },
        {
            "use_case": "Plagiarism and LLM-copy triage for instructors",
            "example": (
                "Two submissions reach a similarity of 0.93 against the 0.85 threshold, so the "
                "agent raises a flag in the report. The instructor reviews only those pairs instead of all 300."
            ),
            "benefit": "Saves review time by narrowing manual checking to suspicious cases.",
        },
        {
            "use_case": "Continuous self-check pre-submission hook for students",
            "example": (
                "Students run c-autograder locally before pushing to Git; the sanitizer_run and "
                "edge_case_runner analyzers catch signed 32-bit overflow and off-by-one bugs early."
            ),
            "benefit": "Teaches defensive C programming habits through concrete failing inputs.",
        },
    ],
    "limitations": [
        {
            "limitation": "Finite I/O tests cannot prove mathematical correctness",
            "example": (
                "A submission passes all 10 hidden tests but fails when the input has extra "
                "whitespace or a trailing newline that no test covers, or hardcodes a lookup table "
                "for small inputs. The agent still reports 10/10 on correctness."
            ),
            "mitigation": (
                "Combine fixed regression tests with property-based randomized fuzzing against a "
                "reference oracle binary."
            ),
        },
        {
            "limitation": "Empirical timing curves can misclassify complexity on noisy hosts",
            "example": (
                "An O(n) loop with a tiny constant factor finishes in 0.4ms for n=1..100 while OS "
                "scheduling jitter adds 0.8ms of variance, causing complexity_estimator to label an "
                "O(n) algorithm as O(1) (or vice versa)."
            ),
            "mitigation": (
                "Combine AST loop-bound static analysis with hardware instruction counters (perf) "
                "rather than wall-clock time alone."
            ),
        },
        {
            "limitation": "Token-shingle similarity can false-positive on short boilerplate problems",
            "example": (
                "For a 10-line 'add two integers' task, two independent students who write standard "
                "scanf/printf with a helper function can exceed 0.85 token cosine similarity despite "
                "zero collusion."
            ),
            "mitigation": (
                "Discount template boilerplate tokens and require a minimum AST node count before "
                "raising a similarity flag."
            ),
        },
        {
            "limitation": "Heuristic / LLM readability rubrics can be gamed with superficial comments",
            "example": (
                "A student adds meaningless comments ('// function') and long meaningless variable "
                "names ('variable_one_number') over spaghetti logic, receiving 10/10 on readability."
            ),
            "mitigation": (
                "Cross-check comment semantic relevance against AST operations and enforce human TA "
                "spot checks on borderline style scores."
            ),
        },
    ],
}


def evaluate_submission(
    submission_path: str | Path,
    rules_path: str | Path,
    workspace_root: str | Path | None = None,
) -> Dict[str, Any]:
    """Run the full coordinator pipeline on a C submission and return the structured report."""
    sub_path = Path(submission_path).resolve()
    r_path = Path(rules_path).resolve()
    root = Path(workspace_root).resolve() if workspace_root else r_path.parent.parent

    rules: GradingRules = load_rules(r_path)
    source_code = sub_path.read_text(encoding="utf-8", errors="replace")

    first_pass, compile_res = run_first_pass(
        sub_path,
        sample_input=rules.sample_input,
        time_limit_s=rules.time_limit_s,
        memory_limit_mb=rules.memory_limit_mb,
    )

    flags: List[str] = []
    if first_pass.suspected_infinite_loop:
        flags.append("suspected_infinite_loop")
    if not first_pass.compiled:
        flags.append("compilation_failed")

    outcomes: List[AnalyzerOutcome] = []
    try:
        for metric in rules.metrics:
            analyzer_fn = ANALYZER_REGISTRY.get(metric.analyzer)
            if analyzer_fn is None:
                raise KeyError(f"Unknown analyzer '{metric.analyzer}' for metric '{metric.name}'.")

            if first_pass.suspected_infinite_loop and metric.analyzer in EXECUTION_ANALYZERS:
                outcomes.append(
                    AnalyzerOutcome(
                        name=metric.name,
                        analyzer=metric.analyzer,
                        score=0.0,
                        weight=metric.weight,
                        contribution=0.0,
                        verdict="skipped (smoke run timed out)",
                        feedback="Skipped execution-based analyzer because smoke test timed out.",
                        evidence={"skipped": True, "reason": "suspected_infinite_loop"},
                    )
                )
                continue

            ctx = AnalyzerContext(
                source_path=sub_path,
                source_code=source_code,
                binary_path=compile_res.binary_path,
                workspace_root=root,
                time_limit_s=rules.time_limit_s,
                memory_limit_mb=rules.memory_limit_mb,
                params=metric.params,
            )
            outcome = analyzer_fn(ctx, metric.name, metric.weight)
            outcomes.append(outcome)
            if outcome.analyzer == "similarity_flag" and outcome.evidence.get("flagged"):
                flags.append("suspected_plagiarism_or_llm_copy")
    finally:
        if compile_res.binary_path and compile_res.binary_path.is_file():
            try:
                os.remove(compile_res.binary_path)
            except OSError:
                pass

    total_grade = round(sum(o.contribution for o in outcomes), 2)

    return {
        "submission": sub_path.name,
        "problem": rules.problem,
        "rules_hash": rules.rules_hash,
        "grade": total_grade,
        "first_pass": asdict(first_pass),
        "metrics": [asdict(o) for o in outcomes],
        "flags": flags,
        "usefulness_limitations": USEFULNESS_AND_LIMITATIONS,
        "tool_versions": {
            "c_compiler": get_compiler_version(),
            "autograder": "0.1.0",
        },
    }


def format_student_text_report(report: Dict[str, Any]) -> str:
    """Render the human-readable text report for students."""
    lines: List[str] = []
    lines.append(f"===== Grading report for {report['submission']} =====")
    lines.append(f"Problem: {report['problem']} (Rules: {report['rules_hash']})")
    lines.append(f"Overall grade: {report['grade']:.1f} / 100")
    lines.append("")
    lines.append(f"{'Metric':<15} {'Weight':<7} {'Score':<8} {'Contribution':<13} {'Verdict'}")
    lines.append("-" * 72)

    failing_cases: List[Dict[str, Any]] = []
    suggestions: List[str] = []

    for m in report["metrics"]:
        w_pct = int(round(m["weight"] * 100))
        pts = round(m["score"] * w_pct, 1)
        score_str = f"{pts:g}/{w_pct}"
        contrib_str = f"{m['contribution']:.1f}"
        lines.append(
            f"{m['name']:<15} {w_pct:<7} {score_str:<8} {contrib_str:<13} {m['verdict']}"
        )
        if m["name"] == "correctness":
            failing_cases.extend(m.get("evidence", {}).get("failing", []))
        for sug in m.get("suggestions", []):
            if sug not in suggestions:
                suggestions.append(sug)

    if failing_cases:
        lines.append("")
        lines.append("--- Where you failed ---")
        for fc in failing_cases:
            lines.append(f"Test {fc.get('test_id', 'case')} INPUT:    {fc['input']}")
            lines.append(f"        EXPECTED: {fc['expected']}")
            lines.append(f"        GOT:      {fc['got']} ({fc['note']})")
            lines.append(f"        WHY:      {fc.get('why', fc['note'])}")

    if suggestions:
        lines.append("")
        lines.append("--- Suggestions to raise the grade ---")
        for sug in suggestions:
            lines.append(f"- {sug}")

    lines.append("")
    lines.append("--- Usefulness & limitations of this evaluation ---")
    lines.append("Useful for:")
    for idx, item in enumerate(report["usefulness_limitations"]["usefulness"], start=1):
        lines.append(f"{idx}. {item['use_case']}")
        lines.append(f"   Example: {item['example']}")
        lines.append(f"   Benefit: {item['benefit']}")

    lines.append("")
    lines.append("Limits of this report:")
    for idx, item in enumerate(report["usefulness_limitations"]["limitations"], start=1):
        lines.append(f"{idx}. {item['limitation']}")
        lines.append(f"   Example: {item['example']}")
        lines.append(f"   Fix:     {item['mitigation']}")

    return "\n".join(lines) + "\n"


def write_reports(report: Dict[str, Any], out_dir: str | Path) -> tuple[Path, Path]:
    """Write both machine-readable JSON and student-facing text reports to disk."""
    target_dir = Path(out_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(report["submission"]).stem
    json_path = target_dir / f"{stem}.json"
    txt_path = target_dir / f"{stem}.txt"

    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    txt_path.write_text(format_student_text_report(report), encoding="utf-8")
    return json_path, txt_path
