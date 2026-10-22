"""External grading rule loader, validator, and canonical SHA-256 hashing."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List


@dataclass(frozen=True)
class MetricRule:
    """Configuration for a single grading metric and its expert analyzer."""

    name: str
    analyzer: str
    weight: float
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GradingRules:
    """Complete external rule set defining limits and weighted metrics."""

    problem: str
    time_limit_s: float
    memory_limit_mb: int
    metrics: List[MetricRule]
    rules_hash: str
    sample_input: str = "7 5\n"


class RuleValidationError(ValueError):
    """Raised when an instructor rules file is malformed or weights do not sum to 1.0."""


def compute_canonical_rules_hash(raw_data: Dict[str, Any]) -> str:
    """Compute a deterministic SHA-256 digest of the canonicalized rules JSON."""
    canonical = json.dumps(raw_data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    return f"sha256:{digest[:16]}"


def load_rules(path: str | Path) -> GradingRules:
    """Load and validate an instructor grading rules file from disk."""
    rule_path = Path(path)
    if not rule_path.is_file():
        raise FileNotFoundError(f"Grading rules file not found: {rule_path}")

    with rule_path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)

    if not isinstance(raw, dict):
        raise RuleValidationError("Top-level rules JSON must be an object.")

    problem = str(raw.get("problem", "")).strip()
    if not problem:
        raise RuleValidationError("Rules file must specify a non-empty 'problem' identifier.")

    time_limit_s = float(raw.get("time_limit_s", 1.0))
    memory_limit_mb = int(raw.get("memory_limit_mb", 64))
    if time_limit_s <= 0 or memory_limit_mb <= 0:
        raise RuleValidationError("time_limit_s and memory_limit_mb must be positive.")

    raw_metrics = raw.get("metrics")
    if not isinstance(raw_metrics, list) or not raw_metrics:
        raise RuleValidationError("Rules file must contain a non-empty 'metrics' list.")

    metrics: List[MetricRule] = []
    total_weight = 0.0
    for idx, item in enumerate(raw_metrics):
        if not isinstance(item, dict):
            raise RuleValidationError(f"Metric at index {idx} must be an object.")
        name = str(item.get("name", "")).strip()
        analyzer = str(item.get("analyzer", "")).strip()
        if not name or not analyzer:
            raise RuleValidationError(f"Metric at index {idx} requires 'name' and 'analyzer'.")
        weight = float(item.get("weight", 0.0))
        if weight < 0.0 or weight > 1.0:
            raise RuleValidationError(f"Metric '{name}' has invalid weight {weight}.")
        params = item.get("params") or {}
        if not isinstance(params, dict):
            raise RuleValidationError(f"Metric '{name}' params must be a JSON object.")
        metrics.append(MetricRule(name=name, analyzer=analyzer, weight=weight, params=params))
        total_weight += weight

    if abs(total_weight - 1.0) > 1e-6:
        raise RuleValidationError(
            f"Metric weights must sum to 1.00 (got {total_weight:.4f})."
        )

    sample_input = str(raw.get("sample_input", "7 5\n"))
    return GradingRules(
        problem=problem,
        time_limit_s=time_limit_s,
        memory_limit_mb=memory_limit_mb,
        metrics=metrics,
        rules_hash=compute_canonical_rules_hash(raw),
        sample_input=sample_input,
    )
