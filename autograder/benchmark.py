"""Benchmark timing report generator for comparing multiple C submissions."""

from __future__ import annotations

from typing import Any, Dict, List


def summarize_complexity_timings(reports: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract empirical timing curves from evaluated submission reports."""
    rows: List[Dict[str, Any]] = []
    for rep in reports:
        for m in rep.get("metrics", []):
            if m.get("analyzer") == "complexity_estimator":
                samples = m.get("evidence", {}).get("timing_samples", [])
                rows.append(
                    {
                        "submission": rep.get("submission", "unknown"),
                        "bound": m.get("evidence", {}).get("required_bound", "O(1)"),
                        "samples": samples,
                    }
                )
    return rows
