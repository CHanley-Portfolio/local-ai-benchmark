"""
Application request for executing one complete benchmark suite.
"""

from dataclasses import dataclass

from .benchmark_case_plan import BenchmarkCasePlan


@dataclass(frozen=True)
class BenchmarkExecutionRequest:
    """
    describe one complete benchmark-suite execution.

    This request contains everything the application layer needs to execute, score, and persist a benchmark run.

    Database connection management and backend implementation details remain outside this contract.
    """

    benchmark_suite_id: int

    case_plans: tuple[BenchmarkCasePlan, ...]

    model_profile_id: int
    hardware_profile_id: int
    runtime_profile_id: int
    context_profile_id: int | None

    source_git_commit: str | None
    run_mode: str
    notes: str | None = None