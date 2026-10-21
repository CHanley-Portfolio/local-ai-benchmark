"""
PostgreSQL integration tests for historical benchmark-run comparison.
"""

import asyncio

from sqlalchemy.orm import Session

from local_ai_benchmark import BenchmarkRunner
from local_ai_benchmark.application.benchmark_execution_request_builder import (
    BenchmarkExecutionRequestBuilder,
)
from local_ai_benchmark.application.benchmark_execution_service import (
    BenchmarkExecutionService,
)
from local_ai_benchmark.application.benchmark_run_comparison_service import (
    BenchmarkRunComparisonService,
)
from local_ai_benchmark.application.benchmark_run_coordinator import (
    BenchmarkRunCoordinator,
)
from local_ai_benchmark.inference import InferenceRequest, InferenceResult
from local_ai_benchmark.persistence.seeding import seed_benchmark_test_data
from local_ai_benchmark.scoring import create_default_scorer_registry


class HistoricalComparisonInferenceExecutor:
    """
    Deterministic executor used to create historical comparison evidence.
    """

    def __init__(
        self,
        *,
        response_text: str,
        total_duration_ns: int,
        output_eval_duration_ns: int,
    ) -> None:
        self._response_text = response_text
        self._total_duration_ns = total_duration_ns
        self._output_eval_duration_ns = output_eval_duration_ns

    async def chat(
        self,
        inference_request: InferenceRequest,
    ) -> InferenceResult:
        """
        Return deterministic inference evidence for one historical run.
        """

        return InferenceResult(
            model_name=inference_request.model_name,
            response_text=self._response_text,
            total_duration_ns=self._total_duration_ns,
            output_token_count=1,
            output_eval_duration_ns=self._output_eval_duration_ns,
        )


def _execute_historical_run(
    *,
    benchmark_database_session: Session,
    benchmark_suite_id: int,
    model_profile_id: int,
    hardware_profile_id: int,
    runtime_profile_id: int,
    context_profile_id: int,
    source_git_commit: str,
    inference_executor: HistoricalComparisonInferenceExecutor,
) -> int:
    """
    Execute and persist one historical benchmark run through production layers.
    """

    request_builder = BenchmarkExecutionRequestBuilder(
        benchmark_database_session
    )

    execution_request = request_builder.build(
        benchmark_suite_id=benchmark_suite_id,
        model_profile_id=model_profile_id,
        hardware_profile_id=hardware_profile_id,
        runtime_profile_id=runtime_profile_id,
        context_profile_id=context_profile_id,
        source_git_commit=source_git_commit,
        run_mode="integration_test",
    )

    benchmark_runner = BenchmarkRunner(
        inference_executor
    )

    benchmark_run_coordinator = BenchmarkRunCoordinator(
        database_session=benchmark_database_session,
        scorer_registry=create_default_scorer_registry(),
    )

    benchmark_execution_service = BenchmarkExecutionService(
        database_session=benchmark_database_session,
        benchmark_runner=benchmark_runner,
        benchmark_run_coordinator=benchmark_run_coordinator,
    )

    execution_result = asyncio.run(
        benchmark_execution_service.execute(
            execution_request
        )
    )

    return execution_result.benchmark_run_id


def test_historical_runner_generated_runs_can_be_compared(
    benchmark_database_session: Session,
) -> None:
    """
    Verify historical runner-generated runs expose objective regressions.

    The baseline returns the exact expected answer and generates 20 tokens per
    second.

    The comparison run returns an incorrect answer and generates 10 tokens per
    second.

    Historical comparison should report the quality and pass regression while
    preserving the performance difference as measured evidence.
    """

    seed_ids = seed_benchmark_test_data(
        benchmark_database_session
    )

    baseline_run_id = _execute_historical_run(
        benchmark_database_session=benchmark_database_session,
        benchmark_suite_id=seed_ids.benchmark_suite_id,
        model_profile_id=seed_ids.model_profile_id,
        hardware_profile_id=seed_ids.hardware_profile_id,
        runtime_profile_id=seed_ids.runtime_profile_id,
        context_profile_id=seed_ids.context_profile_id,
        source_git_commit="comparison-baseline",
        inference_executor=HistoricalComparisonInferenceExecutor(
            response_text="ready",
            total_duration_ns=1_500_000_000,
            output_eval_duration_ns=50_000_000,
        ),
    )

    comparison_run_id = _execute_historical_run(
        benchmark_database_session=benchmark_database_session,
        benchmark_suite_id=seed_ids.benchmark_suite_id,
        model_profile_id=seed_ids.model_profile_id,
        hardware_profile_id=seed_ids.hardware_profile_id,
        runtime_profile_id=seed_ids.runtime_profile_id,
        context_profile_id=seed_ids.context_profile_id,
        source_git_commit="comparison-regression",
        inference_executor=HistoricalComparisonInferenceExecutor(
            response_text="wrong",
            total_duration_ns=2_000_000_000,
            output_eval_duration_ns=100_000_000,
        ),
    )

    comparison_service = BenchmarkRunComparisonService(
        benchmark_database_session
    )

    run_comparison = comparison_service.compare_runs(
        baseline_run_id=baseline_run_id,
        comparison_run_id=comparison_run_id,
    )

    assert run_comparison.baseline_run_id == baseline_run_id
    assert run_comparison.comparison_run_id == comparison_run_id

    assert run_comparison.benchmark_suite_id == (
        seed_ids.benchmark_suite_id
    )

    assert run_comparison.total_case_count == 1

    assert run_comparison.pass_regression_count == 1
    assert run_comparison.execution_regression_count == 0
    assert run_comparison.quality_regression_count == 1
    assert run_comparison.quality_improvement_count == 0

    assert run_comparison.has_regressions is True

    case_comparison = run_comparison.case_comparisons[0]

    assert case_comparison.benchmark_case_id == (
        seed_ids.benchmark_case_id
    )

    assert case_comparison.baseline_result_status == "completed"
    assert case_comparison.comparison_result_status == "completed"

    assert case_comparison.baseline_quality_score == 100
    assert case_comparison.comparison_quality_score == 0
    assert case_comparison.quality_score_delta == -100

    assert case_comparison.baseline_passed is True
    assert case_comparison.comparison_passed is False
    assert case_comparison.pass_regressed is True
    assert case_comparison.execution_regressed is False

    assert case_comparison.baseline_output_tokens_per_second == 20
    assert case_comparison.comparison_output_tokens_per_second == 10
    assert case_comparison.output_tokens_per_second_delta == -10

    assert case_comparison.baseline_total_duration_ns == 1_500_000_000
    assert case_comparison.comparison_total_duration_ns == 2_000_000_000
    assert case_comparison.total_duration_delta_ns == 500_000_000