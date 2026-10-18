"""
Machine-readable result returned by the benchmark application service.
"""

from dataclasses import dataclass

from local_ai_benchmark.execution import BenchmarkRunSummary


@dataclass(frozen=True)
class BenchmarkExecutionResult:
    """
    Return the execution summary and durable database identifiers for one run. 

    Attributes:
        benchmark_run_id:
            Durable PostgreSQL identifier for the completed benchmark run.

        benchmark_case_result_ids:
            Ordered durable identifiers for the persisted case results. 
        
        benchmark_run_summary:
            Immutable execution summary produced by BenchmarkRunner.
    """

    benchmark_run_id: int
    benchmark_case_result_ids: tuple[int, ...]
    benchmark_run_summary: BenchmarkRunSummary