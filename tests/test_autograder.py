"""End-to-end unit and reproducibility tests for c-autograder."""

from __future__ import annotations

import unittest
from pathlib import Path

from autograder.coordinator import evaluate_submission
from autograder.rules import RuleValidationError, load_rules


REPO_ROOT = Path(__file__).resolve().parent.parent


class TestAutoGraderReproducibility(unittest.TestCase):
    def test_rules_loader_computes_deterministic_hash(self) -> None:
        rules_path = REPO_ROOT / "rules" / "add_two_integers.json"
        r1 = load_rules(rules_path)
        r2 = load_rules(rules_path)
        self.assertEqual(r1.rules_hash, r2.rules_hash)
        self.assertTrue(r1.rules_hash.startswith("sha256:"))
        self.assertEqual(len(r1.metrics), 9)

    def test_reproducible_grade_on_flawed_add_submission(self) -> None:
        sub = REPO_ROOT / "submissions" / "add.c"
        rules = REPO_ROOT / "rules" / "add_two_integers.json"
        rep1 = evaluate_submission(sub, rules, workspace_root=REPO_ROOT)
        rep2 = evaluate_submission(sub, rules, workspace_root=REPO_ROOT)
        self.assertEqual(rep1["grade"], rep2["grade"])
        self.assertEqual(rep1["rules_hash"], rep2["rules_hash"])
        self.assertTrue(rep1["first_pass"]["compiled"])
        self.assertTrue(rep1["first_pass"]["smoke_ok"])

    def test_perfect_submission_scores_full_marks(self) -> None:
        sub = REPO_ROOT / "submissions" / "add_perfect.c"
        rules = REPO_ROOT / "rules" / "add_two_integers.json"
        rep = evaluate_submission(sub, rules, workspace_root=REPO_ROOT)
        self.assertEqual(rep["grade"], 100.0)
        self.assertEqual(rep["flags"], [])

    def test_infinite_loop_submission_is_contained_and_flagged(self) -> None:
        sub = REPO_ROOT / "submissions" / "add_infinite.c"
        rules = REPO_ROOT / "rules" / "add_two_integers.json"
        rep = evaluate_submission(sub, rules, workspace_root=REPO_ROOT)
        self.assertTrue(rep["first_pass"]["suspected_infinite_loop"])
        self.assertIn("suspected_infinite_loop", rep["flags"])


if __name__ == "__main__":
    unittest.main()
