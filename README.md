# c-autograder

Rule-driven automated grading engine and sandboxed evaluator for C submissions.

`c-autograder` reads an instructor-defined JSON ruleset, runs a fast sanity pass (compilation, smoke test under fixed wall-clock and memory limits, and static structure checks), dispatches independent metric analyzers, and generates deterministic JSON and student-facing text reports.

## Highlights

- **Deterministic & Reproducible**: Same C submission + same JSON ruleset (verified via SHA-256 rules hash) always produces the exact same grade.
- **Sandboxed Execution**: Enforces wall-clock timeouts (`time_limit_s`) and address-space/memory limits (`memory_limit_mb`), surviving infinite loops and crashes cleanly.
- **Modular Expert Analyzers**:
  - `io_tests`: Hidden I/O test runner with counterexample extraction.
  - `compiler_warnings`: Strict `gcc`/`clang` warning inspection (`-Wall -Wextra -std=c11`).
  - `static_analysis`: Cyclomatic complexity, function length, and header hygiene checks.
  - `function_split`: Modularity and helper function decomposition verifier.
  - `edge_case_runner`: Targeted boundary & overflow probe (`INT_MAX + 1`, zero, negatives, formatting).
  - `complexity_estimator`: Empirical timing curve regression against target asymptotic bounds (`O(1)`, `O(n)`, `O(n log n)`).
  - `sanitizer_run`: AddressSanitizer (`ASan`) and UndefinedBehaviorSanitizer (`UBSan`) dynamic instrumentation.
  - `llm_review`: Deterministic style & readability evaluation (supports local Ollama or heuristic fallback at `temperature=0, seed=42`).
  - `similarity_flag`: Token shingle Jaccard/Cosine similarity and LLM-boilerplate fingerprinter against submission corpora.

## Quick Start

```bash
python3 -m autograder.cli submissions/add.c --rules rules/add_two_integers.json --out-dir reports/
```

## License

MIT License — Ajay Srivatsan R
