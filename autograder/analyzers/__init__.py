"""Expert analyzers for grading C submissions across orthogonal metrics."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


@dataclass
class AnalyzerContext:
    """Inputs forwarded by the coordinator to each expert analyzer."""

    source_path: Path
    source_code: str
    binary_path: Optional[Path]
    workspace_root: Path
    time_limit_s: float
    memory_limit_mb: int
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalyzerOutcome:
    """Normalized result returned by an expert analyzer."""

    name: str
    analyzer: str
    score: float  # Normalized 0.0 .. 1.0
    weight: float
    contribution: float
    verdict: str
    feedback: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    suggestions: List[str] = field(default_factory=list)


AnalyzerFunc = Callable[[AnalyzerContext, str, float], AnalyzerOutcome]
