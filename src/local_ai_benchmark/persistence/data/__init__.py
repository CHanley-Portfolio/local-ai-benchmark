"""
Data contracts used by Benchmark Service persistence workflows.
"""

from .benchmark_run_persistence_request import (
    BenchmarkRunPersistenceRequest as BenchmarkRunPersistenceRequest,
)
from .benchmark_run_persistence_result import (
    BenchmarkRunPersistenceResult as BenchmarkRunPersistenceResult,
)

__all__ = [
    "BenchmarkRunPersistenceRequest",
    "BenchmarkRunPersistenceResult",
]
