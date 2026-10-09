"""
Association between one persisted benchmark case result and its quality score.

Execution and scoring intentionally happen before persistence.

This contract tells the persistence layer which BenchmarkCaseScore belongs to which 
already-created BenchmarkCaseResult row without coupling the scoring package to SQLAlchemy models.
"""

from dataclasses import dataclass

from local_ai_benchmark.scoring import BenchmarkCaseScore


@dataclass(frozen=True)
class BenchmarkCaseScorePersistence:
    """
    Associate one durable case-result record with its scoring evidence,

    Attributes:
        benchmark_case_result_id: 
            Primary key of BenchmarkCaseResult row that should receive the aggregate quality result.
        benchmark_case_score:
            Immutable quality-scoring result produced by a BenchmarkScorer implementation.
    """
    
    benchmark_case_result_id: int
    benchmark_case_score: BenchmarkCaseScore