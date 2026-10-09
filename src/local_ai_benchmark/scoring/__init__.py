"""
Benchmark quality-scoring infrastructure.

Scoring is intentionally separate from benchmark execution and persistence.

BenchmarkRunner determines whether inference executed successfully.

Scorers determine whether a completed model or router response satisfies the
benchmark case's evaluation requirements.

Persistence records both forms of evidence without making either layer depend
on PostgreSQL implementation details.
"""

from .data import BenchmarkCaseScore as BenchmarkCaseScore
from .data import BenchmarkCriterionScore as BenchmarkCriterionScore
from .data import BenchmarkScoringRequest as BenchmarkScoringRequest
from .default_scorer_registry import (
    create_default_scorer_registry as create_default_scorer_registry,
)
from .exact_scorer import ExactScorer as ExactScorer
from .scorer import BenchmarkScorer as BenchmarkScorer
from .scorer_registry import BenchmarkScorerRegistry as BenchmarkScorerRegistry

__all__ = [
    "BenchmarkCaseScore",
    "BenchmarkCriterionScore",
    "BenchmarkScorer",
    "BenchmarkScoringRequest",
    "ExactScorer",
    "BenchmarkScorerRegistry",
    "create_default_scorer_registry",
]