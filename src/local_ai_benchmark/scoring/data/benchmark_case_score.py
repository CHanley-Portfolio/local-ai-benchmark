"""
Aggregate quality result for one scored benchmark case.
"""

from dataclasses import dataclass
from decimal import Decimal

from .benchmark_criterion_score import BenchmarkCriterionScore


@dataclass(frozen=True)
class BenchmarkCaseScore:
    """
    represent the complete quality-scoring result for one benchmark case

    This object is deliberately seperate from BenchmarkCaseExecution.

    BenchmarkCaseExecution describes whether inference successfully happened.
    BenchmarkCaseScore describes whether the resulting answer satisfied the benchmark's quality requirements.

    A model response can therefore have:
        execution status = completed
        quality passed = False

    That distinction is essential. Successfully generating text 
    does not mean the model answered the benchmark correctly.

    Attributes:
        benchmark_case_id:
            Persistent identifier of teh benchmark case that was evaluated.

        normalized_quality_score:
            Aggregate case quality expressed on teh standard 0-100 scale.

        passed:
            Whether the completed benchmark case satisfied its pass rule.

        criterion_scors:
            Immutable criterion-level evidence used to calculate the aggregate
            quality result.

            Deterministic benchmarks may contain only one criterion while
            rubric benchmarks may contain several.

        scorer_type:
            Stable identifier for the scoring mechanism used for this case.

        scorer_version:
            Optional implementation/version identifier.

        diagnostic_text:
            Optional human-readable scoring explanation useful for debugging, 
            benchmark review, and historical analysis.
    """

    benchmark_case_id: int

    normalized_quality_score: Decimal
    passed: bool

    criterion_scores: tuple[BenchmarkCriterionScore, ...]

    scorer_type: str
    scorer_version: str | None = None

    diagnostic_text: str | None = None