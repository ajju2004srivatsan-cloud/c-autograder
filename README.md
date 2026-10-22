# c-autograder

Rule-driven automated grading engine and sandboxed evaluator for C submissions.

`c-autograder` reads an external instructor-defined JSON ruleset, runs a fast first-pass sanity sweep (compilation, resource-bounded smoke test, and static structure checks), dispatches 9 specialized metric analyzers, and generates deterministic machine-readable JSON (`reports/<submission>.json`) and student-facing text (`reports/<submission>.txt`) reports.

## Architecture

```text
Student C Submission (add.c)  +  External Rules JSON (rules/add_two_integers.json)
                                      │
                                      ▼
                     ┌────────────────────────────────┐
                     │  Coordinator First-Pass Sweep  │
                     │  1. Compile check (-Wall -std) │
                     │  2. Sandboxed smoke test (1s)  │
                     │  3. Static entry/IO sanity     │
                     └────────────────┬───────────────┘
                                      │
            ┌─────────────────────────┼─────────────────────────┐
            ▼                         ▼                         ▼
   [Execution Analyzers]     [Static Analyzers]      [Style & Originality]
   - io_tests (20%)          - compiler_warnings     - llm_review (T=0, seed=42)
   - edge_case_runner (10%)  - static_analysis       - similarity_flag (3-gram)
   - complexity_estimator    - function_split
   - sanitizer_run (ASan)
            │                         │                         │
            └─────────────────────────┼─────────────────────────┘
                                      ▼
                Deterministic Collation & Dual Report Output
                - reports/add.json (SHA-256 rules hash + evidence)
                - reports/add.txt  (Student table + counterexamples)
```

## Quick Start

### 1. Grade a single C submission

```bash
python3 -m autograder.cli submissions/add.c \
  --rules rules/add_two_integers.json \
  --out-dir reports/
```

### 2. Sample Student Report Output (`reports/add.txt`)

```text
===== Grading report for add.c =====
Problem: add_two_integers (Rules: sha256:a0abe2c08f9d7470)
Overall grade: 77.0 / 100

Metric          Weight  Score    Contribution  Verdict
------------------------------------------------------------------------
correctness     20      16/20    16.0          8 of 10 tests pass
syntax          10      9/10     9.0           -Wunused-result x1
structure       10      6/10     6.0           single-block code, no helper prototypes
modularity      10      3/10     3.0           only main() defined
logical         10      8/10     8.0           INT_MAX + 1 overflow not handled
complexity      10      10/10    10.0          O(1) confirmed
memory_safety   10      10/10    10.0          ASan/UBSan clean
readability     10      5/10     5.0           no comments, terse single-letter names, cramped formatting / missing whitespace
originality     10      10/10    10.0          max similarity 0.32 (safe)

--- Where you failed ---
Test 07_int_max_overflow INPUT:    2147483647 1
        EXPECTED: 2147483648
        GOT:      -2147483648 (runtime error: signed 32-bit integer overflow wrapped around)
        WHY:      a + b overflows on 32-bit signed ints. Use long long or check that b <= INT_MAX - a before adding.
```

### 3. Run Unit & Reproducibility Suite

```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```

### 4. Docker Sandboxed Execution

```bash
docker build -t c-autograder .
docker run --rm c-autograder submissions/add.c --rules rules/add_two_integers.json
```

## Usefulness & Limitations in Real-Life Settings

### Real-Life Use Cases
1. **Large-Enrollment CS1/CS2 University Courses**: Grades hundreds of weekly C lab uploads in seconds with zero TA variance and immediate counterexample feedback.
2. **Coding-Interview & Embedded Systems Hiring Screens**: Filters candidate C submissions by correctness, integer overflow resilience, and AddressSanitizer cleanliness.
3. **Plagiarism & Boilerplate Triage**: Computes lexical 3-gram cosine similarity across the submission corpus so instructors only inspect pairs exceeding `flag_threshold`.
4. **Pre-Submission Student Self-Check CLI**: Lets students catch ignored `scanf` return values, missing helper functions, and 32-bit overflow locally before pushing.

### Concrete Limitations & Mitigations
1. **Finite I/O Tests Cannot Prove Mathematical Correctness**: A program that hardcodes edge cases or fails on an untested input still scores 10/10 on `io_tests`. *Mitigation*: Pair fixed test suites with randomized property-based fuzzing against a reference binary.
2. **Empirical Timing Curves Are Sensitive to OS Jitter**: On a busy host, sub-millisecond `O(n)` loops over small sizes (`1..100`) can appear flat (`O(1)`). *Mitigation*: Combine AST loop-nesting inspection with hardware instruction counters (`perf`).
3. **Token Similarity False Positives on Short Programs**: On a 10-line task, two independent solutions using standard `scanf`/`printf` can share high token overlap. *Mitigation*: Discount template tokens and require a minimum AST node count before flagging.
4. **Readability Heuristics Can Be Gamed by Superficial Comments**: Adding trivial comments (`// comment`) and verbose variable names over convoluted logic inflates static style scores. *Mitigation*: Use semantic AST-aware LLM prompts at `T=0` with human TA spot checks.

## License

MIT License — Ajay Srivatsan R
