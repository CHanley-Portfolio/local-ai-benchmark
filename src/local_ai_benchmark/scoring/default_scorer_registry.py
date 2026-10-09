"""
Default Benchmark Service scorer-registry construction.

This module defines which scoring implementations are currently available in
the production Benchmark Service configuration.
"""

from .exact_scorer import ExactScorer
from .scorer_registry import BenchmarkScorerRegistry


def create_default_scorer_registry() -> BenchmarkScorerRegistry:
    """
    Create the default Benchmark Service scorer registry.

    Returns:
        BenchmarkScorerRegistry:
            Registry containing all scoring implementations currently
            supported by the Benchmark Service.

    Design:
        Keep scorer construction centralized here.

        As new scoring mechanisms are implemented, such as rubric or
        exact-with-explanation scoring, they can be registered here without
        changing benchmark orchestration code.
    """

    return BenchmarkScorerRegistry(
        {
            "exact": ExactScorer(),
        }
    )