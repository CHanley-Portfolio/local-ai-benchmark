"""
Normalized input supplied to Benchmark Service scoring implementations.

The scoring layer should not depend directly on SQLAlchemy ORM models.

Instead, orchestration code converts benchmark definitions and observed
execution evidence into this immutable scoring request.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BenchmarkScoringRequest:
    """
    Describe everything required to score one benchmark case.
    """

    benchmark_case_id: int

    evaluation_target: str
    scoring_method: str

    response_text: str | None = None
    route_mode: str | None = None

    expected_answer: str | None = None
    expected_route_mode: str | None = None

    expected_criteria: tuple[str, ...] = ()