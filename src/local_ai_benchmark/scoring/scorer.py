"""
Protocol implemented by Benchmark Service quality scorers.

Scoring implementations may use ver different mechanisms, but callers should not need
scorer-specific code siply to obtain a normalized BenchmarkCaseScore.
"""

from typing import Protocol, runtime_checkable

from .data import BenchmarkCaseScore, BenchmarkScoringRequest


@runtime_checkable
class BenchmarkScorer(Protocol):
    """
    Define the behavior from a benchmark quality scorer.
    
    Concrete implementations may include:
        - exact deterministic comparison;
        - rubric evaluation;
        - schema validation;
        - executable generated- code tests;
        - retrieval evaluation;
        - future model-assisted evaluation.
    
    All scorers receive the same normalized BenchmarkScoringRequest and return the same normalized BenchmarkCaseScore contract.
    This allows the Benchmark Service to support multiple scoring methods without requiring scorer-specific code in the orchestration layer;
    and prevents the scoring implementation from depending on the persistence layer or SQLAlchemy ORM models.
    """

    def score(self, scoring_request: BenchmarkScoringRequest) -> BenchmarkCaseScore:
        """
        Score one benchmark case.

        Args:
            scoring_request:
                Normalized benchmark definition and observed result.

        Returns:
            BenchmarkCaseScore:
                Immutable quality result containing the aggregate score and the exact-match criterion evidence.
        """
