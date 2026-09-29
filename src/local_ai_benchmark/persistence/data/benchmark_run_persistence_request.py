"""
Persistence request for one completed BenchmarkRunner suite execution.
"""

from dataclasses import dataclass

from local_ai_benchmark.execution import BenchmarkRunSummary


@dataclass(frozen=True)
class BenchmarkRunPersistenceRequest:
    """
    Describe the durable metadata required to persist one benchmark run.

    BenchmarkRunner intentionally produces execution evidence without knowing
    about SQLAlchemy or PostgreSQL. This request combines that execution
    summary with the persistent environment/profile identifiers needed by the
    benchmark database.
    """

    benchmark_run_summary: BenchmarkRunSummary

    model_profile_id: int
    hardware_profile_id: int
    runtime_profile_id: int
    context_profile_id: int | None

    source_git_commit: str | None
    run_mode: str
    notes: str | None = None
