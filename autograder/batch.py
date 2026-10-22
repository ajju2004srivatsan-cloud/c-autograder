"""Batch grading runner for evaluating an entire directory of C submissions."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List

from autograder.coordinator import evaluate_submission, write_reports


def evaluate_directory(
    submissions_dir: str | Path,
    rules_path: str | Path,
    out_dir: str | Path,
) -> List[Dict[str, Any]]:
    """Evaluate all .c files in a directory and emit a summary leaderboard CSV."""
    sub_dir = Path(submissions_dir).resolve()
    target_out = Path(out_dir).resolve()
    target_out.mkdir(parents=True, exist_ok=True)

    results: List[Dict[str, Any]] = []
    for c_file in sorted(sub_dir.glob("*.c")):
        rep = evaluate_submission(c_file, rules_path)
        write_reports(rep, target_out)
        results.append(rep)

    csv_path = target_out / "summary.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["submission", "problem", "grade", "compiled", "smoke_ok", "flags"])
        for r in results:
            writer.writerow(
                [
                    r["submission"],
                    r["problem"],
                    r["grade"],
                    r["first_pass"]["compiled"],
                    r["first_pass"]["smoke_ok"],
                    ";".join(r["flags"]),
                ]
            )
    return results
