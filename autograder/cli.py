"""Command-line interface for running c-autograder unattended."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from autograder.coordinator import (
    evaluate_submission,
    format_student_text_report,
    write_reports,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="c-autograder",
        description="Rule-driven automated grading engine for C submissions.",
    )
    parser.add_argument(
        "submission",
        type=Path,
        help="Path to the student's C source file (e.g. submissions/add.c)",
    )
    parser.add_argument(
        "--rules",
        type=Path,
        required=True,
        help="Path to the instructor's JSON grading rules file",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("reports"),
        help="Directory where <submission>.json and <submission>.txt reports are written",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress printing the student text report to stdout",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    report = evaluate_submission(args.submission, args.rules)
    json_path, txt_path = write_reports(report, args.out_dir)

    if not args.quiet:
        sys.stdout.write(format_student_text_report(report))
        sys.stdout.write(f"\n[Saved JSON report to {json_path} and text report to {txt_path}]\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
