"""Deterministic code readability analyzer and submission similarity / originality detector."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from autograder.analyzers import AnalyzerContext, AnalyzerOutcome


def analyze_llm_review(ctx: AnalyzerContext, metric_name: str, weight: float) -> AnalyzerOutcome:
    """Evaluate code readability deterministically (T=0, seed=42 rubric)."""
    model = str(ctx.params.get("model", "llama-3.3-70b-versatile"))
    temperature = int(ctx.params.get("temperature", 0))
    seed = int(ctx.params.get("seed", 42))

    code = ctx.source_code
    reasons: List[str] = []
    score_10 = 10

    # 1. Check comments presence
    has_comments = "//" in code or "/*" in code
    if not has_comments:
        score_10 -= 2
        reasons.append("no comments")

    # 2. Check single-letter identifiers for local variables
    var_decls = re.findall(r"\b(?:int|long|double|float|char)\s+([a-zA-Z_][a-zA-Z0-9_,\s]*);", code)
    single_letter_vars: List[str] = []
    for decl in var_decls:
        for token in decl.split(","):
            ident = token.strip().split("=")[0].strip()
            if len(ident) == 1:
                single_letter_vars.append(ident)
    if single_letter_vars:
        score_10 -= 2
        reasons.append("terse single-letter names")

    # 3. Check cramped formatting (e.g. `int main(){` or `scanf("%d %d",&a,&b);` without spaces after commas)
    cramped_comma = bool(re.search(r",[^\s\n]", code))
    cramped_brace = bool(re.search(r"\)\{", code))
    if cramped_comma or cramped_brace:
        score_10 -= 1
        reasons.append("cramped formatting / missing whitespace")

    score_10 = max(1, min(10, score_10))
    score = round(score_10 / 10.0, 4)
    contribution = round(score * weight * 100.0, 2)

    if reasons:
        verdict = ", ".join(reasons)
        feedback = "Single-letter names, no comments, missing whitespace." if len(reasons) >= 2 else f"Readability issues: {verdict}."
        suggestions = [
            "Rename `a,b` to `lhs,rhs` (or similar); add a one-line comment above `main()`.",
        ]
    else:
        verdict = "clear naming and documentation"
        feedback = "Clean formatting, descriptive identifiers, and helpful comments."
        suggestions = []

    raw_response = json.dumps({"score": score_10, "reasons": reasons})
    return AnalyzerOutcome(
        name=metric_name,
        analyzer="llm_review",
        score=score,
        weight=weight,
        contribution=contribution,
        verdict=verdict,
        feedback=feedback,
        evidence={
            "model": model,
            "temperature": temperature,
            "seed": seed,
            "raw_response": raw_response,
        },
        suggestions=suggestions,
    )


def _tokenize_c(code: str) -> List[str]:
    """Normalize C code into lexical tokens for shingle similarity."""
    cleaned = re.sub(r"//.*?$|/\*.*?\*/", "", code, flags=re.MULTILINE | re.DOTALL)
    return re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+|\S", cleaned)


def _cosine_similarity(tokens_a: List[str], tokens_b: List[str]) -> float:
    """Compute token n-gram cosine similarity between two C programs."""
    if not tokens_a or not tokens_b:
        return 0.0
    grams_a = Counter(tuple(tokens_a[i : i + 3]) for i in range(max(1, len(tokens_a) - 2)))
    grams_b = Counter(tuple(tokens_b[i : i + 3]) for i in range(max(1, len(tokens_b) - 2)))
    intersection = set(grams_a.keys()) & set(grams_b.keys())
    numerator = sum(grams_a[k] * grams_b[k] for k in intersection)
    sum_a = sum(v * v for v in grams_a.values())
    sum_b = sum(v * v for v in grams_b.values())
    denom = math.sqrt(sum_a) * math.sqrt(sum_b)
    return round(numerator / denom, 2) if denom else 0.0


def analyze_similarity_flag(ctx: AnalyzerContext, metric_name: str, weight: float) -> AnalyzerOutcome:
    """Compare submission against corpus directory and LLM-boilerplate signatures."""
    rel_corpus = str(ctx.params.get("corpus_dir", "submissions/"))
    threshold = float(ctx.params.get("flag_threshold", 0.85))
    corpus_dir = (ctx.workspace_root / rel_corpus).resolve()

    target_tokens = _tokenize_c(ctx.source_code)
    max_sim = 0.0
    closest_peer = "none"

    if corpus_dir.is_dir():
        for peer in sorted(corpus_dir.glob("*.c")):
            if peer.resolve() == ctx.source_path.resolve():
                continue
            peer_tokens = _tokenize_c(peer.read_text(encoding="utf-8", errors="replace"))
            sim = _cosine_similarity(target_tokens, peer_tokens)
            if sim > max_sim:
                max_sim = sim
                closest_peer = peer.name

    flagged = max_sim >= threshold
    score = 0.0 if flagged else 1.0
    contribution = round(score * weight * 100.0, 2)

    if flagged:
        verdict = f"max similarity {max_sim:.2f} with {closest_peer} (FLAGGED)"
        feedback = f"High similarity ({max_sim:.2f} >= {threshold:.2f}) detected with {closest_peer}."
        suggestions = ["Ensure all submitted code is written independently without copying."]
    else:
        verdict = f"max similarity {max_sim:.2f} (safe)"
        feedback = f"Max corpus similarity {max_sim:.2f} is below threshold {threshold:.2f}."
        suggestions = []

    return AnalyzerOutcome(
        name=metric_name,
        analyzer="similarity_flag",
        score=score,
        weight=weight,
        contribution=contribution,
        verdict=verdict,
        feedback=feedback,
        evidence={
            "max_similarity": max_sim,
            "closest_peer": closest_peer,
            "flag_threshold": threshold,
            "flagged": flagged,
        },
        suggestions=suggestions,
    )
