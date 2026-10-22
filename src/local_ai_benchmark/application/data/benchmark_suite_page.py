"""
Paginated application result containign benchmark-suite summaries.
"""

from dataclasses import dataclass

from .benchmark_suite_summary import BenchmarkSuiteSummary


@dataclass(frozen=True)
class BenchmarkSuitePage:
    """
    Represent one page of benchmark suites plus the complete filtered count.
    """

    items: tuple[BenchmarkSuiteSummary, ...]
    total_count: int