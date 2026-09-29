"""
Durable identifiers created while persisting one benchmark run.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BenchmarkRunPersistenceResult:
    """
    Identify the durable database records created for one benchmark run.
    """

    benchmark_run_id: int
    benchmark_case_result_ids: tuple[int, ...]
