"""
PostgreSQL integration tests for BenchmarkExecutionRequestBuilder.
"""

from decimal import Decimal

from sqlalchemy.orm import Session

from local_ai_benchmark.application.benchmark_execution_request_builder import (
    BenchmarkExecutionRequestBuilder,
)
from local_ai_benchmark.persistence.seeding import seed_benchmark_test_data


def test_execution_request_builder_loads_persisted_suite_configuration(
    benchmark_database_session: Session,
) -> None:
    """
    Verify persisted suite and model configuration becomes an execution plan.
    """

    seed_ids = seed_benchmark_test_data(
        benchmark_database_session
    )

    builder = BenchmarkExecutionRequestBuilder(
        benchmark_database_session
    )

    execution_request = builder.build(
        benchmark_suite_id=seed_ids.benchmark_suite_id,
        model_profile_id=seed_ids.model_profile_id,
        hardware_profile_id=seed_ids.hardware_profile_id,
        runtime_profile_id=seed_ids.runtime_profile_id,
        context_profile_id=seed_ids.context_profile_id,
        source_git_commit="request-builder-integration",
        run_mode="integration_test",
    )

    assert execution_request.benchmark_suite_id == (
        seed_ids.benchmark_suite_id
    )

    assert execution_request.model_profile_id == (
        seed_ids.model_profile_id
    )

    assert len(execution_request.case_plans) == 1

    case_plan = execution_request.case_plans[0]

    assert case_plan.case_request.benchmark_case_id == (
        seed_ids.benchmark_case_id
    )

    assert case_plan.evaluation_target == "model"
    assert case_plan.scoring_method == "exact"
    assert case_plan.expected_answer == "ready"
    assert case_plan.expected_criteria == ()

    inference_request = case_plan.case_request.inference_request

    assert inference_request.model_name == "seed_test_model:q4"
    assert inference_request.user_message == (
        "Return exactly the word ready."
    )
    assert inference_request.thinking_enabled is False

    assert inference_request.temperature == Decimal("0")
    assert inference_request.top_p == Decimal("1")
    assert inference_request.seed == 1
    assert inference_request.max_output_tokens == 256