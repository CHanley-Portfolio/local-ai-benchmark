"""
Historical benchmark-run comparison application service.

BenchmarkRunComparisonService reads already-persisted benchmark evidence 
and produces an immutable machine-readable comparison.

It does not modify benchmark history or apply subjective regrssion thresholds.
"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from local_ai_benchmark.persistence.models import (
    BenchmarkCaseResult,
    BenchmarkPerformanceMetric,
    BenchmarkRun,
)

from .data.benchmark_case_comparison import BenchmarkCaseComparison
from .data.benchmark_run_comparison import BenchmarkRunComparison


class BenchmarkRunComparisonService:
    """
    Compare two persisted executions of the same benchmark suite.

    Version 1 reports objective changes only.

    Quality regression:
        comparison normalized quality score is lower than baseline.

    Pass regression:
        baseline passed and comparison failed.

    Execution regression:
        baseline inference completed but comparison inference did not complete.

    Performance differences are reported as numeric deltas but are not automatically classified as regressions 
    because acceptable performance thresholds have not yet been defined.
    """

    def __init__(self, database_session: Session) -> None:
        """
        Create the historical comparison service.

        Args:
            database_session:
                SQLAlchemy session used to read persisted benchmark history.
        """

        self._database_session = database_session

    def compare_runs(self, *, baseline_run_id: int, comparison_run_id: int) -> BenchmarkRunComparison:
        """
        Compare two historical benchmark runs.

        Args:
            baseline_run_id:
                Existing historical run used as the reference point.

            comparison_run_id:
                Later or alternative historical run being evaluated.

        Returns:
            BenchmarkRunComparison:
                Machine-readable case-level and aggregate comparison evidence.

        Raises:
            ValueError:
                raised when a run does not exist, the same run is supplied twice, 
                the run belongs to different benchmark suites, or their persisted
                case sets do not match.
        """

        if baseline_run_id == comparison_run_id:
            raise ValueError("Baseline and comparison benchmark runs must be different.")

        baseline_run = self._database_session.get(BenchmarkRun, baseline_run_id)

        if baseline_run is None:
            raise ValueError(f"Baseline benchmark run {baseline_run_id} does not exist.")

        comparison_run = self._database_session.get(BenchmarkRun, comparison_run_id)

        if comparison_run is None:
            raise ValueError(f"Comparison benchmark run {comparison_run_id} does not exist.")

        if (baseline_run.benchmark_suite_id != comparison_run.benchmark_suite_id):
            raise ValueError("Historical benchmark runs must use the same benchmark suite before their case results can be compared.")

        baseline_results = self._load_case_results(baseline_run_id)
        comparison_results = self._load_case_results(comparison_run_id)

        baseline_case_ids = set(baseline_results)
        comparison_case_ids = set(comparison_results)

        if baseline_case_ids != comparison_case_ids:
            raise ValueError("Historical benchmark runs contain different benchmark case result sets and connot be compared directly.")

        case_comparisons: list[BenchmarkCaseComparison] = []

        for benchmark_case_id in sorted(baseline_case_ids):
            baseline_case_result, baseline_performance = baseline_results[benchmark_case_id]

            comparison_case_result, comparison_performance = comparison_results[benchmark_case_id]

            quality_score_delta = self._decimal_delta(baseline_case_result.normalized_quality_score, comparison_case_result.normalized_quality_score)

            output_tokens_per_second_delta = self._decimal_delta(
                (
                    baseline_performance.output_tokens_per_second
                    if baseline_performance is not None
                    else None
                ),
                (
                    comparison_performance.output_tokens_per_second
                    if comparison_performance is not None
                    else None
                ),
            )

            total_duration_delta_ns = self._decimal_delta(
                (
                    baseline_performance.total_duration_ns
                    if baseline_performance is not None
                    else None
                ),
                (
                    comparison_performance.total_duration_ns
                    if comparison_performance is not None
                    else None
                ),
            )

            case_comparisons.append(
                BenchmarkCaseComparison(
                    benchmark_case_id=benchmark_case_id,
                    baseline_result_status=baseline_case_result.result_status,
                    comparison_result_status=comparison_case_result.result_status,
                    baseline_quality_score=baseline_case_result.normalized_quality_score,
                    comparison_quality_score=comparison_case_result.normalized_quality_score,
                    quality_score_delta=quality_score_delta,
                    baseline_passed=baseline_case_result.passed,
                    comparison_passed=comparison_case_result.passed,
                    pass_regressed=baseline_case_result.passed is True and comparison_case_result.passed is False,
                    execution_regressed=baseline_case_result.result_status == "completed" and comparison_case_result.result_status != "completed",
                    baseline_output_tokens_per_second=(
                        baseline_performance.output_tokens_per_second
                        if baseline_performance is not None
                        else None
                    ),
                    comparison_output_tokens_per_second=(
                        comparison_performance.output_tokens_per_second
                        if comparison_performance is not None
                        else None
                    ),
                    output_tokens_per_second_delta=output_tokens_per_second_delta,
                    baseline_total_duration_ns=(
                        baseline_performance.total_duration_ns
                        if baseline_performance is not None
                        else None
                    ),
                    comparison_total_duration_ns=(
                        comparison_performance.total_duration_ns
                        if comparison_performance is not None
                        else None
                    ),
                    total_duration_delta_ns=total_duration_delta_ns
                )
            )

        case_comparison_tuple = tuple(case_comparisons)

        quality_regression_count = sum(
            case_comparison.quality_score_delta is not None
            and case_comparison.quality_score_delta < 0
            for case_comparison in case_comparison_tuple
        )

        quality_improvement_count = sum(
            case_comparison.quality_score_delta is not None
            and case_comparison.quality_score_delta > 0
            for case_comparison in case_comparison_tuple
        )

        pass_regression_count = sum(
            case_comparison.pass_regressed
            for case_comparison in case_comparison_tuple
        )

        execution_regression_count = sum(
            case_comparison.execution_regressed 
            for case_comparison in case_comparison_tuple
        )

        return BenchmarkRunComparison(
            baseline_run_id=baseline_run_id,
            comparison_run_id=comparison_run_id,
            benchmark_suite_id=baseline_run.benchmark_suite_id,
            
            baseline_model_profile_id=baseline_run.model_profile_id,
            baseline_hardware_profile_id=baseline_run.hardware_profile_id,
            baseline_runtime_profile_id=baseline_run.runtime_profile_id,
            baseline_context_profile_id=baseline_run.context_profile_id,
            baseline_source_git_commit=baseline_run.source_git_commit,

            comparison_model_profile_id=comparison_run.model_profile_id,
            comparison_hardware_profile_id=comparison_run.hardware_profile_id,
            comparison_runtime_profile_id=comparison_run.runtime_profile_id,
            comparison_context_profile_id=comparison_run.context_profile_id,
            comparison_source_git_commit=comparison_run.source_git_commit,
            
            case_comparisons=case_comparison_tuple,
            total_case_count=len(case_comparison_tuple),
            pass_regression_count=pass_regression_count,
            execution_regression_count=execution_regression_count,
            quality_regression_count=quality_regression_count,
            quality_improvement_count=quality_improvement_count,
            has_regressions=(
                pass_regression_count > 0
                or execution_regression_count > 0
                or quality_regression_count > 0
            ),
        )

    def _load_case_results(self, benchmark_run_id: int) -> dict[int, tuple[BenchmarkCaseResult, BenchmarkPerformanceMetric | None]]:
        """
        Load Case results and optional performance telemetry for one run.
        """

        result_rows = self._database_session.execute(
            select(
                BenchmarkCaseResult,
                BenchmarkPerformanceMetric,
            )
            .outerjoin(
                BenchmarkPerformanceMetric,
                BenchmarkPerformanceMetric.benchmark_case_result_id
                == BenchmarkCaseResult.benchmark_case_result_id,
            )
            .where(
                BenchmarkCaseResult.benchmark_run_id == benchmark_run_id
            )
        ).all()

        return {
            benchmark_case_result.benchmark_case_id: (
                benchmark_case_result,
                performance_metric,
            )
            for benchmark_case_result, performance_metric in result_rows
        }

    @staticmethod
    def _decimal_delta( baseline_value: Decimal | None, comparison_value: Decimal | None) -> int | None:
        """
        Calculate comparison minus baseline for optional Decimal metrics
        """

        if baseline_value is None or comparison_value is None:
            return None
        
        return comparison_value - baseline_value 
