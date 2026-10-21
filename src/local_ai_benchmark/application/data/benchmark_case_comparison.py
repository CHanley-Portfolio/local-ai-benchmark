"""
Machine-readable comparison of one benchamark case across two historical runs.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class BenchmarkCaseComparison:
    """
    Compare one benchmark case between a baseline and comparison run.

    Delta convention:
        comparison value - baseline value

    Therefore:
        positive quality delta menas quality improved;
        negative quality delta means quality regressed;
        positive throughput delta means genereation became faster;
        positive duration delta means execution took longer.
    """

    benchmark_case_id: int

    baseline_result_status: str
    comparison_result_status: str

    baseline_quality_score: Decimal | None
    comparison_quality_score: Decimal | None
    quality_score_delta: Decimal | None

    baseline_passed: bool | None
    comparison_passed: bool | None

    pass_regressed: bool
    execution_regressed: bool

    baseline_output_tokens_per_second: Decimal | None
    comparison_output_tokens_per_second: Decimal | None
    output_tokens_per_second_delta: Decimal | None

    baseline_total_duration_ns: int | None
    comparison_total_duration_ns: int | None
    total_duration_delta_ns: int | None