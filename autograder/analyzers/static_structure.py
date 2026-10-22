"""Static structure, cyclomatic complexity, and function-split modularity analyzers."""

from __future__ import annotations

import re
from typing import Any, Dict, List

from autograder.analyzers import AnalyzerContext, AnalyzerOutcome


FUNC_DEF_PATTERN = re.compile(
    r"^\s*(?:static\s+|inline\s+)*(?:unsigned\s+|signed\s+|long\s+|short\s+)*"
    r"[A-Za-z_][A-Za-z0-9_\s\*]*\b([A-Za-z_][A-Za-z0-9_]*)\s*\([^;]*\)\s*\{",
    re.MULTILINE,
)

CONTROL_KEYWORDS = re.compile(r"\b(if|else\s+if|for|while|case|catch|\?|\&\&|\|\|)\b")


def extract_c_functions(source_code: str) -> List[Dict[str, Any]]:
    """Extract function names, line counts, and cyclomatic complexity from C source."""
    functions: List[Dict[str, Any]] = []
    for match in FUNC_DEF_PATTERN.finditer(source_code):
        fn_name = match.group(1)
        if fn_name in ("if", "for", "while", "switch"):
            continue
        start_brace = match.end() - 1
        depth = 0
        end_idx = len(source_code)
        for idx in range(start_brace, len(source_code)):
            ch = source_code[idx]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end_idx = idx + 1
                    break
        body = source_code[start_brace:end_idx]
        lines = [ln for ln in body.splitlines() if ln.strip()]
        cyclomatic = 1 + len(CONTROL_KEYWORDS.findall(body))
        functions.append(
            {
                "name": fn_name,
                "length_lines": len(lines),
                "cyclomatic": cyclomatic,
            }
        )
    return functions


def analyze_static_analysis(ctx: AnalyzerContext, metric_name: str, weight: float) -> AnalyzerOutcome:
    """Evaluate code structure: cyclomatic complexity, function length, and header/guard hygiene."""
    max_cyclomatic = int(ctx.params.get("max_cyclomatic", 8))
    max_fn_len = int(ctx.params.get("max_function_length", 40))

    functions = extract_c_functions(ctx.source_code)
    issues: List[str] = []
    score = 1.0

    # Check if everything is crammed into a single block with no prototypes or helper declarations
    if len(functions) <= 1:
        score -= 0.40
        issues.append("single-block code, no helper prototypes")

    for fn in functions:
        if fn["cyclomatic"] > max_cyclomatic:
            score -= 0.25
            issues.append(f"{fn['name']}() cyclomatic={fn['cyclomatic']} > {max_cyclomatic}")
        if fn["length_lines"] > max_fn_len:
            score -= 0.25
            issues.append(f"{fn['name']}() length={fn['length_lines']} > {max_fn_len}")

    score = round(max(0.0, score), 4)
    contribution = round(score * weight * 100.0, 2)
    verdict = ", ".join(issues) if issues else "clean structure"
    feedback = (
        f"Static structure issues: {verdict}."
        if issues
        else "All functions meet cyclomatic complexity and length bounds."
    )

    return AnalyzerOutcome(
        name=metric_name,
        analyzer="static_analysis",
        score=score,
        weight=weight,
        contribution=contribution,
        verdict=verdict,
        feedback=feedback,
        evidence={
            "functions": functions,
            "max_cyclomatic_allowed": max_cyclomatic,
            "max_function_length_allowed": max_fn_len,
            "issues": issues,
        },
        suggestions=(
            ["Separate business logic from I/O in `main()` and declare clear function prototypes."]
            if issues
            else []
        ),
    )


def analyze_function_split(ctx: AnalyzerContext, metric_name: str, weight: float) -> AnalyzerOutcome:
    """Evaluate modularity by checking whether helper functions are extracted outside main()."""
    min_functions = int(ctx.params.get("min_functions", 2))
    functions = extract_c_functions(ctx.source_code)
    fn_names = [f["name"] for f in functions]
    fn_count = len(functions)

    if fn_count >= min_functions:
        score = 1.0
        verdict = f"{fn_count} functions defined ({', '.join(fn_names)})"
        feedback = f"Good modularity: {fn_count} functions defined (minimum {min_functions})."
        suggestions: List[str] = []
    elif fn_count == 1:
        score = 0.30
        verdict = "only main() defined"
        feedback = "Only main() is defined. Extract an add(long long, long long) helper."
        suggestions = ["Extract `long long add(long long a, long long b)` into its own function; call it from `main`."]
    else:
        score = 0.0
        verdict = "no functions detected"
        feedback = "No valid C function definitions detected."
        suggestions = ["Define `main()` and dedicated helper functions."]

    contribution = round(score * weight * 100.0, 2)
    return AnalyzerOutcome(
        name=metric_name,
        analyzer="function_split",
        score=score,
        weight=weight,
        contribution=contribution,
        verdict=verdict,
        feedback=feedback,
        evidence={
            "functions_defined": fn_count,
            "function_names": fn_names,
            "expected_min": min_functions,
        },
        suggestions=suggestions,
    )
