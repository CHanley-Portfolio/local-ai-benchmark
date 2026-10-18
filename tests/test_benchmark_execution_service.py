"""
PostgreSQL integration tests for BenchmarkExecutionService.

These tests exercise the complete Benchmark Service application workflow:

    application request
    -> BenchmarkRunner
    -> inference executor
    -> BenchmarkRunCoordinator
    -> ExactScorer
    -> PostgreSQL persistence
    -> machine-readable application result

A deterministic fake inference executor is used so the test exercises the
Benchmark Service itself without requiring Ollama, a GPU, or a loaded model.
"""

import asyncio
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from local_ai_benchmark import BenchmarkCaseRequest, BenchmarkRunner
from local_ai_benchmark.application import (
    BenchmarkCasePlan,
    BenchmarkExecutionRequest,
    BenchmarkExecutionService,
    BenchmarkRunCoordinator,
)
from local_ai_benchmark.inference import InferenceRequest, InferenceResult
from local_ai_benchmark.persistence.models import (
    BenchmarkCaseResult,
    BenchmarkPerformanceMetric,
    BenchmarkQualityScore,
    BenchmarkRun,
)
from local_ai_benchmark.persistence.seeding import seed_benchmark_test_data
from local_ai_benchmark.scoring import create_default_scorer_registry


class SuccessfulBenchmarkInferenceExecutor:
    """
    Deterministic inference executor for application integration testing.

    The executor records the request it receives so the test can prove that the
    application service actually passed the planned inference request through
    BenchmarkRunner rather than bypassing execution.
    """

    def __init__(self) -> None:
        self.received_request: InferenceRequest | None = None

    async def chat(
        self,
        inference_request: InferenceRequest,
    ) -> InferenceResult:
        """
        Return one deterministic successful benchmark response.
        """

        self.received_request = inference_request

        return InferenceResult(
            model_name=inference_request.model_name,
            response_text="ready",
            total_duration_ns=1_500_000_000,
            model_load_duration_ns=100_000_000,
            prompt_token_count=5,
            prompt_eval_duration_ns=250_000_000,
            output_token_count=1,
            output_eval_duration_ns=50_000_000,
            backend_metrics={
                "done_reason": "stop",
            },
        )


def test_benchmark_execution_service_runs_scores_and_persists_suite(
    benchmark_database_session: Session,
) -> None:
    """
    Verify one top-level application call completes the benchmark lifecycle.

    This is the first integration test that does not manually construct a
    BenchmarkRunSummary.

    BenchmarkExecutionService must cause the runner to execute inference,
    construct scoring evidence, persist performance and quality data, commit
    its unit of work, and return durable identifiers.
    """

    seed_ids = seed_benchmark_test_data(benchmark_database_session)

    inference_request = InferenceRequest(
        model_name="seed_test_model:q4",
        user_message="Return exactly the word ready.",
        thinking_enabled=False,
    )

    case_plan = BenchmarkCasePlan(
        case_request=BenchmarkCaseRequest(
            benchmark_case_id=seed_ids.benchmark_case_id,
            inference_request=inference_request,
        ),
        evaluation_target="model",
        scoring_method="exact",
        expected_answer="ready",
    )

    fake_inference_executor = SuccessfulBenchmarkInferenceExecutor()

    benchmark_runner = BenchmarkRunner(
        fake_inference_executor
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
            BenchmarkExecutionRequest(
                benchmark_suite_id=seed_ids.benchmark_suite_id,
                case_plans=(case_plan,),
                model_profile_id=seed_ids.model_profile_id,
                hardware_profile_id=seed_ids.hardware_profile_id,
                runtime_profile_id=seed_ids.runtime_profile_id,
                context_profile_id=seed_ids.context_profile_id,
                source_git_commit="execution-service-integration",
                run_mode="integration_test",
                notes=(
                    "Executed through BenchmarkExecutionService "
                    "integration test."
                ),
            )
        )
    )

    # Prove the planned request actually passed through BenchmarkRunner and
    # reached the inference boundary.
    assert fake_inference_executor.received_request is inference_request

    # Verify the machine-readable application result.
    assert execution_result.benchmark_run_id > 0
    assert len(execution_result.benchmark_case_result_ids) == 1

    assert execution_result.benchmark_run_summary.status == "completed"
    assert execution_result.benchmark_run_summary.total_case_count == 1
    assert execution_result.benchmark_run_summary.completed_case_count == 1
    assert execution_result.benchmark_run_summary.failed_case_count == 0

    benchmark_case_result_id = (
        execution_result.benchmark_case_result_ids[0]
    )

    # Verify the benchmark run itself was persisted.
    persisted_run = benchmark_database_session.get(
        BenchmarkRun,
        execution_result.benchmark_run_id,
    )

    assert persisted_run is not None
    assert persisted_run.status == "completed"
    assert persisted_run.source_git_commit == (
        "execution-service-integration"
    )
    assert persisted_run.benchmark_suite_id == (
        seed_ids.benchmark_suite_id
    )

    # Verify raw execution evidence and aggregate quality.
    persisted_case_result = benchmark_database_session.get(
        BenchmarkCaseResult,
        benchmark_case_result_id,
    )

    assert persisted_case_result is not None
    assert persisted_case_result.result_status == "completed"
    assert persisted_case_result.raw_model_response == "ready"
    assert persisted_case_result.normalized_quality_score == Decimal("100")
    assert persisted_case_result.passed is True

    # Verify performance telemetry travelled from inference -> runner ->
    # persistence rather than being manufactured by the test.
    persisted_performance = benchmark_database_session.get(
        BenchmarkPerformanceMetric,
        benchmark_case_result_id,
    )

    assert persisted_performance is not None
    assert persisted_performance.total_duration_ns == 1_500_000_000
    assert persisted_performance.model_load_duration_ns == 100_000_000
    assert persisted_performance.prompt_token_count == 5
    assert persisted_performance.output_token_count == 1

    assert persisted_performance.prompt_tokens_per_second == Decimal("20")
    assert persisted_performance.output_tokens_per_second == Decimal("20")

    assert persisted_performance.backend_metrics == {
        "done_reason": "stop",
    }

    # Verify criterion-level scoring evidence also reached PostgreSQL.
    persisted_quality_scores = benchmark_database_session.scalars(
        select(BenchmarkQualityScore).where(
            BenchmarkQualityScore.benchmark_case_result_id
            == benchmark_case_result_id
        )
    ).all()

    assert len(persisted_quality_scores) == 1

    persisted_quality_score = persisted_quality_scores[0]

    assert persisted_quality_score.criterion_name == (
        "response_exact_match"
    )
    assert persisted_quality_score.raw_score == Decimal("1")
    assert persisted_quality_score.max_score == Decimal("1")
    assert persisted_quality_score.normalized_score == Decimal("100")
    assert persisted_quality_score.passed is True
    assert persisted_quality_score.scorer_type == "exact"
    assert persisted_quality_score.scorer_version == "1"