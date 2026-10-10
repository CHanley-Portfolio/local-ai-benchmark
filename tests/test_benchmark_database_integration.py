"""
PostgreSQL integration tests for benchmark persistence.

These tests exercise the real PostgreSQL schema rather than SQLAlchemy
metadata alone.

They are intentionally restricted to the ``local_ai_benchmark_test`` database.
All benchmark runs and result rows created by a test are wrapped in a
transaction and rolled back afterward so repeated test execution does not
pollute benchmark history.
"""

import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Generator

import pytest
from local_ai_benchmark.application import BenchmarkRunCoordinator
from sqlalchemy import select
from sqlalchemy.orm import Session

from local_ai_benchmark import BenchmarkCaseExecution, BenchmarkRunSummary
from local_ai_benchmark.config import get_benchmark_database_settings
from local_ai_benchmark.inference import InferenceResult
from local_ai_benchmark.persistence import (
    BenchmarkCaseScorePersistence,
    BenchmarkRunPersistenceRequest,
    BenchmarkRunRecorder,
    BenchmarkScoreRecorder,
)
from local_ai_benchmark.persistence.database import create_database_engine
from local_ai_benchmark.persistence.models import (
    BenchmarkCaseResult,
    BenchmarkPerformanceMetric,
    BenchmarkQualityScore,
    BenchmarkRun,
)
from local_ai_benchmark.persistence.seeding import (
    seed_benchmark_test_data,
)
from local_ai_benchmark.scoring import (
    BenchmarkScoringRequest,
    ExactScorer,
    create_default_scorer_registry,
)


@pytest.fixture
def benchmark_database_session() -> Generator[Session, None, None]:
    """
    Provide a transaction-isolated PostgreSQL integration-test session.

    The fixture skips automatically when database credentials are unavailable
    or when the configured database is not ``local_ai_benchmark_test``.

    This keeps the normal unit-test suite safe on machines and CI jobs that do
    not currently provide PostgreSQL integration infrastructure.

    Every database change made through this session is rolled back when the
    test finishes.
    """

    if not os.getenv("LOCAL_AI_BENCHMARK_DB_PASSWORD"):
        pytest.skip("PostgreSQL integration test requires LOCAL_AI_BENCHMARK_DB_PASSWORD.")

    database_settings = get_benchmark_database_settings()

    if database_settings.database_name != "local_ai_benchmark_test":
        pytest.skip(
            "PostgreSQL benchmark integration tests may only run against local_ai_benchmark_test."
        )

    database_engine = create_database_engine(database_settings)

    try:
        with database_engine.connect() as database_connection:
            database_transaction = database_connection.begin()

            try:
                with Session(
                    bind=database_connection,
                    autoflush=False,
                    expire_on_commit=False,
                ) as database_session:
                    yield database_session
            finally:
                database_transaction.rollback()
    finally:
        database_engine.dispose()


def test_multiple_benchmark_runs_are_preserved_and_queryable(
    benchmark_database_session: Session,
) -> None:
    """
    Verify repeated benchmark executions remain separate historical records.

    Two runs use exactly the same suite, model profile, hardware, runtime, and
    benchmark case. Their result quality and performance values differ.

    Querying the history must return both runs independently rather than one
    execution overwriting the other.
    """

    seed_ids = seed_benchmark_test_data(benchmark_database_session)

    first_started_at = datetime(
        2026,
        1,
        1,
        12,
        0,
        tzinfo=timezone.utc,
    )
    second_started_at = first_started_at + timedelta(minutes=10)

    first_run = BenchmarkRun(
        benchmark_suite_id=seed_ids.benchmark_suite_id,
        model_profile_id=seed_ids.model_profile_id,
        hardware_profile_id=seed_ids.hardware_profile_id,
        runtime_profile_id=seed_ids.runtime_profile_id,
        context_profile_id=seed_ids.context_profile_id,
        source_git_commit="integration-test-first",
        run_mode="integration_test",
        status="completed",
        started_at=first_started_at,
        completed_at=first_started_at + timedelta(seconds=5),
        notes="First synthetic historical benchmark run.",
    )

    second_run = BenchmarkRun(
        benchmark_suite_id=seed_ids.benchmark_suite_id,
        model_profile_id=seed_ids.model_profile_id,
        hardware_profile_id=seed_ids.hardware_profile_id,
        runtime_profile_id=seed_ids.runtime_profile_id,
        context_profile_id=seed_ids.context_profile_id,
        source_git_commit="integration-test-second",
        run_mode="integration_test",
        status="completed",
        started_at=second_started_at,
        completed_at=second_started_at + timedelta(seconds=4),
        notes="Second synthetic historical benchmark run.",
    )

    benchmark_database_session.add_all(
        [
            first_run,
            second_run,
        ]
    )
    benchmark_database_session.flush()

    first_result = BenchmarkCaseResult(
        benchmark_run_id=first_run.benchmark_run_id,
        benchmark_case_id=seed_ids.benchmark_case_id,
        result_status="completed",
        raw_model_response="ready",
        normalized_quality_score=Decimal("80"),
        passed=True,
    )

    second_result = BenchmarkCaseResult(
        benchmark_run_id=second_run.benchmark_run_id,
        benchmark_case_id=seed_ids.benchmark_case_id,
        result_status="completed",
        raw_model_response="ready",
        normalized_quality_score=Decimal("95"),
        passed=True,
    )

    benchmark_database_session.add_all(
        [
            first_result,
            second_result,
        ]
    )
    benchmark_database_session.flush()

    benchmark_database_session.add_all(
        [
            BenchmarkQualityScore(
                benchmark_case_result_id=(first_result.benchmark_case_result_id),
                criterion_name="correctness",
                raw_score=Decimal("3.2"),
                max_score=Decimal("4"),
                normalized_score=Decimal("80"),
                passed=True,
                scorer_type="integration_test",
            ),
            BenchmarkQualityScore(
                benchmark_case_result_id=(second_result.benchmark_case_result_id),
                criterion_name="correctness",
                raw_score=Decimal("3.8"),
                max_score=Decimal("4"),
                normalized_score=Decimal("95"),
                passed=True,
                scorer_type="integration_test",
            ),
            BenchmarkPerformanceMetric(
                benchmark_case_result_id=(first_result.benchmark_case_result_id),
                total_duration_ns=5_000_000_000,
                output_token_count=20,
                peak_vram_bytes=8_000_000_000,
            ),
            BenchmarkPerformanceMetric(
                benchmark_case_result_id=(second_result.benchmark_case_result_id),
                total_duration_ns=4_000_000_000,
                output_token_count=20,
                peak_vram_bytes=7_500_000_000,
            ),
        ]
    )

    benchmark_database_session.flush()

    historical_rows = benchmark_database_session.execute(
        select(
            BenchmarkRun.benchmark_run_id,
            BenchmarkRun.started_at,
            BenchmarkCaseResult.normalized_quality_score,
            BenchmarkPerformanceMetric.total_duration_ns,
            BenchmarkPerformanceMetric.peak_vram_bytes,
        )
        .join(
            BenchmarkCaseResult,
            BenchmarkCaseResult.benchmark_run_id == BenchmarkRun.benchmark_run_id,
        )
        .join(
            BenchmarkPerformanceMetric,
            BenchmarkPerformanceMetric.benchmark_case_result_id
            == BenchmarkCaseResult.benchmark_case_result_id,
        )
        .where(
            BenchmarkRun.benchmark_run_id.in_(
                [
                    first_run.benchmark_run_id,
                    second_run.benchmark_run_id,
                ]
            )
        )
        .order_by(BenchmarkRun.started_at)
    ).all()

    assert len(historical_rows) == 2

    first_history_row = historical_rows[0]
    second_history_row = historical_rows[1]

    assert first_history_row.benchmark_run_id == first_run.benchmark_run_id
    assert second_history_row.benchmark_run_id == second_run.benchmark_run_id

    assert first_history_row.normalized_quality_score == Decimal("80")
    assert second_history_row.normalized_quality_score == Decimal("95")

    assert first_history_row.total_duration_ns == 5_000_000_000
    assert second_history_row.total_duration_ns == 4_000_000_000

    assert first_history_row.peak_vram_bytes == 8_000_000_000
    assert second_history_row.peak_vram_bytes == 7_500_000_000

    # Both rows reference the same benchmark configuration. The differing
    # run IDs prove repeated executions are stored as separate history.
    assert first_run.benchmark_suite_id == second_run.benchmark_suite_id
    assert first_run.model_profile_id == second_run.model_profile_id
    assert first_run.hardware_profile_id == second_run.hardware_profile_id
    assert first_run.runtime_profile_id == second_run.runtime_profile_id



def test_benchmark_run_recorder_persists_runner_execution_evidence(
    benchmark_database_session: Session,
) -> None:
    """
    Verify a successful runner summary becomes durable benchmark history.

    The persistence layer should create a BenchmarkRun, BenchmarkCaseResult,
    and BenchmarkPerformanceMetric without requiring BenchmarkRunner itself to
    understand SQLAlchemy.
    """

    seed_ids = seed_benchmark_test_data(benchmark_database_session)

    started_at = datetime(
        2026,
        1,
        2,
        12,
        0,
        tzinfo=timezone.utc,
    )
    completed_at = started_at + timedelta(seconds=2)

    run_summary = BenchmarkRunSummary(
        benchmark_suite_id=seed_ids.benchmark_suite_id,
        status="completed",
        started_at=started_at,
        completed_at=completed_at,
        case_executions=(
            BenchmarkCaseExecution(
                benchmark_case_id=seed_ids.benchmark_case_id,
                status="completed",
                started_at=started_at,
                completed_at=completed_at,
                inference_result=InferenceResult(
                    model_name="seed_test_model:q4",
                    response_text="ready",
                    total_duration_ns=2_000_000_000,
                    model_load_duration_ns=250_000_000,
                    prompt_token_count=20,
                    prompt_eval_duration_ns=1_000_000_000,
                    output_token_count=10,
                    output_eval_duration_ns=500_000_000,
                    backend_metrics={
                        "done_reason": "stop",
                    },
                ),
            ),
        ),
        total_case_count=1,
        completed_case_count=1,
        failed_case_count=0,
    )

    persistence_result = BenchmarkRunRecorder(benchmark_database_session).persist_run(
        BenchmarkRunPersistenceRequest(
            benchmark_run_summary=run_summary,
            model_profile_id=seed_ids.model_profile_id,
            hardware_profile_id=seed_ids.hardware_profile_id,
            runtime_profile_id=seed_ids.runtime_profile_id,
            context_profile_id=seed_ids.context_profile_id,
            source_git_commit="run-recorder-success",
            run_mode="integration_test",
            notes="Persisted from a synthetic BenchmarkRunner summary.",
        )
    )

    assert persistence_result.benchmark_run_id > 0
    assert len(persistence_result.benchmark_case_result_ids) == 1

    persisted_run = benchmark_database_session.get(
        BenchmarkRun,
        persistence_result.benchmark_run_id,
    )

    assert persisted_run is not None
    assert persisted_run.status == "completed"
    assert persisted_run.source_git_commit == "run-recorder-success"
    assert persisted_run.benchmark_suite_id == seed_ids.benchmark_suite_id

    benchmark_case_result_id = persistence_result.benchmark_case_result_ids[0]

    persisted_case_result = benchmark_database_session.get(
        BenchmarkCaseResult,
        benchmark_case_result_id,
    )

    assert persisted_case_result is not None
    assert persisted_case_result.result_status == "completed"
    assert persisted_case_result.raw_model_response == "ready"
    assert persisted_case_result.normalized_quality_score is None
    assert persisted_case_result.passed is None
    assert persisted_case_result.error_type is None
    assert persisted_case_result.error_message is None

    persisted_performance = benchmark_database_session.get(
        BenchmarkPerformanceMetric,
        benchmark_case_result_id,
    )

    assert persisted_performance is not None
    assert persisted_performance.total_duration_ns == 2_000_000_000
    assert persisted_performance.model_load_duration_ns == 250_000_000
    assert persisted_performance.prompt_token_count == 20
    assert persisted_performance.prompt_eval_duration_ns == 1_000_000_000
    assert persisted_performance.prompt_tokens_per_second == Decimal("20")
    assert persisted_performance.output_token_count == 10
    assert persisted_performance.output_eval_duration_ns == 500_000_000
    assert persisted_performance.output_tokens_per_second == Decimal("20")
    assert persisted_performance.backend_metrics == {
        "done_reason": "stop",
    }


def test_benchmark_run_recorder_persists_failed_case_diagnostics(
    benchmark_database_session: Session,
) -> None:
    """
    Verify failed inference remains durable evidence without fake telemetry.
    """

    seed_ids = seed_benchmark_test_data(benchmark_database_session)

    started_at = datetime(
        2026,
        1,
        2,
        13,
        0,
        tzinfo=timezone.utc,
    )
    completed_at = started_at + timedelta(seconds=1)

    run_summary = BenchmarkRunSummary(
        benchmark_suite_id=seed_ids.benchmark_suite_id,
        status="completed_with_failures",
        started_at=started_at,
        completed_at=completed_at,
        case_executions=(
            BenchmarkCaseExecution(
                benchmark_case_id=seed_ids.benchmark_case_id,
                status="failed",
                started_at=started_at,
                completed_at=completed_at,
                inference_result=None,
                error_type="RuntimeError",
                error_message="Synthetic persisted inference failure.",
            ),
        ),
        total_case_count=1,
        completed_case_count=0,
        failed_case_count=1,
    )

    persistence_result = BenchmarkRunRecorder(benchmark_database_session).persist_run(
        BenchmarkRunPersistenceRequest(
            benchmark_run_summary=run_summary,
            model_profile_id=seed_ids.model_profile_id,
            hardware_profile_id=seed_ids.hardware_profile_id,
            runtime_profile_id=seed_ids.runtime_profile_id,
            context_profile_id=seed_ids.context_profile_id,
            source_git_commit="run-recorder-failure",
            run_mode="integration_test",
        )
    )

    persisted_run = benchmark_database_session.get(
        BenchmarkRun,
        persistence_result.benchmark_run_id,
    )

    assert persisted_run is not None
    assert persisted_run.status == "completed_with_failures"

    benchmark_case_result_id = persistence_result.benchmark_case_result_ids[0]

    persisted_case_result = benchmark_database_session.get(
        BenchmarkCaseResult,
        benchmark_case_result_id,
    )

    assert persisted_case_result is not None
    assert persisted_case_result.result_status == "failed"
    assert persisted_case_result.raw_model_response is None
    assert persisted_case_result.error_type == "RuntimeError"
    assert persisted_case_result.error_message == (
        "Synthetic persisted inference failure."
    )

    persisted_performance = benchmark_database_session.get(
        BenchmarkPerformanceMetric,
        benchmark_case_result_id,
    )

    assert persisted_performance is None

def test_exact_score_is_persisted_with_criterion_evidence(
    benchmark_database_session: Session,
) -> None:
    """
    Verify execution, exact scoring, and quality persistence work together.

    This integration test exercises the actual PostgreSQL schema and the
    production scoring/persistence contracts rather than manually inserting
    quality rows.

    The lifecycle under test is:

        BenchmarkRunSummary
            -> BenchmarkRunRecorder
            -> BenchmarkCaseResult
            -> ExactScorer
            -> BenchmarkCaseScore
            -> BenchmarkScoreRecorder
            -> PostgreSQL quality records

    The surrounding test transaction is rolled back by the fixture so no
    synthetic benchmark history remains after the test completes.
    """

    seed_ids = seed_benchmark_test_data(benchmark_database_session)

    started_at = datetime(
        2026,
        1,
        3,
        12,
        0,
        tzinfo=timezone.utc,
    )
    completed_at = started_at + timedelta(seconds=1)

    # First persist the execution evidence exactly as a real benchmark run
    # would. At this stage quality has not yet been evaluated.
    run_summary = BenchmarkRunSummary(
        benchmark_suite_id=seed_ids.benchmark_suite_id,
        status="completed",
        started_at=started_at,
        completed_at=completed_at,
        case_executions=(
            BenchmarkCaseExecution(
                benchmark_case_id=seed_ids.benchmark_case_id,
                status="completed",
                started_at=started_at,
                completed_at=completed_at,
                inference_result=InferenceResult(
                    model_name="seed_test_model:q4",
                    response_text="ready",
                    total_duration_ns=1_000_000_000,
                    output_token_count=1,
                    output_eval_duration_ns=100_000_000,
                ),
            ),
        ),
        total_case_count=1,
        completed_case_count=1,
        failed_case_count=0,
    )

    run_persistence_result = BenchmarkRunRecorder(
        benchmark_database_session
    ).persist_run(
        BenchmarkRunPersistenceRequest(
            benchmark_run_summary=run_summary,
            model_profile_id=seed_ids.model_profile_id,
            hardware_profile_id=seed_ids.hardware_profile_id,
            runtime_profile_id=seed_ids.runtime_profile_id,
            context_profile_id=seed_ids.context_profile_id,
            source_git_commit="exact-score-integration-test",
            run_mode="integration_test",
        )
    )

    benchmark_case_result_id = (
        run_persistence_result.benchmark_case_result_ids[0]
    )

    # Score the observed response through the real deterministic scorer.
    benchmark_case_score = ExactScorer().score(
        BenchmarkScoringRequest(
            benchmark_case_id=seed_ids.benchmark_case_id,
            evaluation_target="model",
            scoring_method="exact",
            response_text="ready",
            expected_answer="ready",
        )
    )

    # Persist the scoring evidence against the already-created case result.
    BenchmarkScoreRecorder(
        benchmark_database_session
    ).persist_case_score(
        BenchmarkCaseScorePersistence(
            benchmark_case_result_id=benchmark_case_result_id,
            benchmark_case_score=benchmark_case_score,
        )
    )

    # Reload the aggregate case result from PostgreSQL.
    persisted_case_result = benchmark_database_session.get(
        BenchmarkCaseResult,
        benchmark_case_result_id,
    )

    assert persisted_case_result is not None
    assert persisted_case_result.raw_model_response == "ready"

    assert (
        persisted_case_result.normalized_quality_score
        == Decimal("100")
    )
    assert persisted_case_result.passed is True

    assert persisted_case_result.diagnostic_text == (
        "Observed value matches expected value"
    )

    # Query the criterion-level evidence independently to prove that the
    # aggregate score was not stored without its underlying scoring record.
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

    assert persisted_quality_score.details == {
        "expected_value": "ready",
        "observed_value": "ready",
    }

def test_benchmark_run_coordinator_persists_and_scores_completed_case(
    benchmark_database_session: Session,
) -> None:
    """
    Verify the application coordinator completes the execution-to-score path.

    The coordinator should:

    1. persist runner execution evidence;
    2. resolve the configured scorer;
    3. evaluate the completed benchmark case;
    4. persist aggregate quality;
    5. persist criterion-level scoring evidence.

    This exercises the real PostgreSQL test database.
    """

    seed_ids = seed_benchmark_test_data(benchmark_database_session)

    started_at = datetime(
        2026,
        1,
        4,
        12,
        0,
        tzinfo=timezone.utc,
    )
    completed_at = started_at + timedelta(seconds=1)

    run_summary = BenchmarkRunSummary(
        benchmark_suite_id=seed_ids.benchmark_suite_id,
        status="completed",
        started_at=started_at,
        completed_at=completed_at,
        case_executions=(
            BenchmarkCaseExecution(
                benchmark_case_id=seed_ids.benchmark_case_id,
                status="completed",
                started_at=started_at,
                completed_at=completed_at,
                inference_result=InferenceResult(
                    model_name="seed_test_model:q4",
                    response_text="ready",
                    total_duration_ns=1_000_000_000,
                    output_token_count=1,
                    output_eval_duration_ns=100_000_000,
                ),
            ),
        ),
        total_case_count=1,
        completed_case_count=1,
        failed_case_count=0,
    )

    coordinator = BenchmarkRunCoordinator(
        database_session=benchmark_database_session,
        scorer_registry=create_default_scorer_registry(),
    )

    persistence_result = coordinator.persist_and_score_run(
        BenchmarkRunPersistenceRequest(
            benchmark_run_summary=run_summary,
            model_profile_id=seed_ids.model_profile_id,
            hardware_profile_id=seed_ids.hardware_profile_id,
            runtime_profile_id=seed_ids.runtime_profile_id,
            context_profile_id=seed_ids.context_profile_id,
            source_git_commit="coordinator-success",
            run_mode="integration_test",
        ),
        scoring_requests=(
            BenchmarkScoringRequest(
                benchmark_case_id=seed_ids.benchmark_case_id,
                evaluation_target="model",
                scoring_method="exact",
                response_text="ready",
                expected_answer="ready",
            ),
        ),
    )

    assert persistence_result.benchmark_run_id > 0
    assert len(persistence_result.benchmark_case_result_ids) == 1

    benchmark_case_result_id = (
        persistence_result.benchmark_case_result_ids[0]
    )

    persisted_case_result = benchmark_database_session.get(
        BenchmarkCaseResult,
        benchmark_case_result_id,
    )

    assert persisted_case_result is not None
    assert persisted_case_result.raw_model_response == "ready"
    assert persisted_case_result.normalized_quality_score == Decimal("100")
    assert persisted_case_result.passed is True

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
    assert persisted_quality_score.normalized_score == Decimal("100")
    assert persisted_quality_score.scorer_type == "exact"
    assert persisted_quality_score.scorer_version == "1"

def test_benchmark_run_coordinator_rejects_duplicate_scoring_requests(
    benchmark_database_session: Session,
) -> None:
    """
    Verify duplicate scoring requests fail before benchmark history is written.

    A benchmark case must have at most one scoring request during a run.
    Ambiguous scoring input must never result in partially persisted history.
    """

    seed_ids = seed_benchmark_test_data(benchmark_database_session)

    started_at = datetime(
        2026,
        1,
        4,
        13,
        0,
        tzinfo=timezone.utc,
    )
    completed_at = started_at + timedelta(seconds=1)

    run_summary = BenchmarkRunSummary(
        benchmark_suite_id=seed_ids.benchmark_suite_id,
        status="completed",
        started_at=started_at,
        completed_at=completed_at,
        case_executions=(
            BenchmarkCaseExecution(
                benchmark_case_id=seed_ids.benchmark_case_id,
                status="completed",
                started_at=started_at,
                completed_at=completed_at,
                inference_result=InferenceResult(
                    model_name="seed_test_model:q4",
                    response_text="ready",
                    total_duration_ns=1_000_000_000,
                    output_token_count=1,
                    output_eval_duration_ns=100_000_000,
                ),
            ),
        ),
        total_case_count=1,
        completed_case_count=1,
        failed_case_count=0,
    )

    persistence_request = BenchmarkRunPersistenceRequest(
        benchmark_run_summary=run_summary,
        model_profile_id=seed_ids.model_profile_id,
        hardware_profile_id=seed_ids.hardware_profile_id,
        runtime_profile_id=seed_ids.runtime_profile_id,
        context_profile_id=seed_ids.context_profile_id,
        source_git_commit="coordinator-duplicate-score",
        run_mode="integration_test",
    )

    scoring_request = BenchmarkScoringRequest(
        benchmark_case_id=seed_ids.benchmark_case_id,
        evaluation_target="model",
        scoring_method="exact",
        response_text="ready",
        expected_answer="ready",
    )

    coordinator = BenchmarkRunCoordinator(
        database_session=benchmark_database_session,
        scorer_registry=create_default_scorer_registry(),
    )

    with pytest.raises(
        ValueError,
        match="Duplicate scoring request",
    ):
        coordinator.persist_and_score_run(
            persistence_request,
            scoring_requests=(
                scoring_request,
                scoring_request,
            ),
        )

    # Duplicate validation occurs before BenchmarkRunRecorder executes, so no
    # partial BenchmarkRun should exist.
    persisted_run = benchmark_database_session.scalar(
        select(BenchmarkRun).where(
            BenchmarkRun.source_git_commit
            == "coordinator-duplicate-score"
        )
    )

    assert persisted_run is None

def test_benchmark_run_coordinator_can_roll_back_partial_run_on_scoring_failure(
    benchmark_database_session: Session,
) -> None:
    """
    Verify a scoring failure can roll back already-flushed execution evidence.

    BenchmarkRunRecorder performs flushes before scoring begins. Therefore an
    application-level failure must remain transactionally reversible.

    A PostgreSQL SAVEPOINT is used here so the integration-test fixture's outer
    transaction remains active after the intentional failure.
    """

    seed_ids = seed_benchmark_test_data(benchmark_database_session)

    started_at = datetime(
        2026,
        1,
        4,
        14,
        0,
        tzinfo=timezone.utc,
    )
    completed_at = started_at + timedelta(seconds=1)

    run_summary = BenchmarkRunSummary(
        benchmark_suite_id=seed_ids.benchmark_suite_id,
        status="completed",
        started_at=started_at,
        completed_at=completed_at,
        case_executions=(
            BenchmarkCaseExecution(
                benchmark_case_id=seed_ids.benchmark_case_id,
                status="completed",
                started_at=started_at,
                completed_at=completed_at,
                inference_result=InferenceResult(
                    model_name="seed_test_model:q4",
                    response_text="ready",
                    total_duration_ns=1_000_000_000,
                    output_token_count=1,
                    output_eval_duration_ns=100_000_000,
                ),
            ),
        ),
        total_case_count=1,
        completed_case_count=1,
        failed_case_count=0,
    )

    coordinator = BenchmarkRunCoordinator(
        database_session=benchmark_database_session,
        scorer_registry=create_default_scorer_registry(),
    )

    with pytest.raises(
        ValueError,
        match="does not have a scoring request",
    ):
        # begin_nested() creates a PostgreSQL SAVEPOINT.
        #
        # BenchmarkRunRecorder will successfully INSERT and flush its rows
        # before the coordinator discovers that scoring input is missing.
        #
        # When the ValueError escapes this context manager, SQLAlchemy rolls
        # the SAVEPOINT back automatically.
        with benchmark_database_session.begin_nested():
            coordinator.persist_and_score_run(
                BenchmarkRunPersistenceRequest(
                    benchmark_run_summary=run_summary,
                    model_profile_id=seed_ids.model_profile_id,
                    hardware_profile_id=seed_ids.hardware_profile_id,
                    runtime_profile_id=seed_ids.runtime_profile_id,
                    context_profile_id=seed_ids.context_profile_id,
                    source_git_commit="coordinator-rollback-test",
                    run_mode="integration_test",
                ),
                scoring_requests=(),
            )

    persisted_run = benchmark_database_session.scalar(
        select(BenchmarkRun).where(
            BenchmarkRun.source_git_commit
            == "coordinator-rollback-test"
        )
    )

    assert persisted_run is None

def test_benchmark_run_coordinator_preserves_failed_case_without_scoring(
    benchmark_database_session: Session,
) -> None:
    """
    Verify failed inference is persisted without fabricated quality evidence.

    An inference failure is useful benchmark history, but there is no valid
    model response to quality-score. The coordinator should therefore preserve
    the failure and continue without requiring a BenchmarkScoringRequest.
    """

    seed_ids = seed_benchmark_test_data(benchmark_database_session)

    started_at = datetime(
        2026,
        1,
        4,
        15,
        0,
        tzinfo=timezone.utc,
    )
    completed_at = started_at + timedelta(seconds=1)

    run_summary = BenchmarkRunSummary(
        benchmark_suite_id=seed_ids.benchmark_suite_id,
        status="completed_with_failures",
        started_at=started_at,
        completed_at=completed_at,
        case_executions=(
            BenchmarkCaseExecution(
                benchmark_case_id=seed_ids.benchmark_case_id,
                status="failed",
                started_at=started_at,
                completed_at=completed_at,
                inference_result=None,
                error_type="RuntimeError",
                error_message="Synthetic coordinator inference failure.",
            ),
        ),
        total_case_count=1,
        completed_case_count=0,
        failed_case_count=1,
    )

    coordinator = BenchmarkRunCoordinator(
        database_session=benchmark_database_session,
        scorer_registry=create_default_scorer_registry(),
    )

    persistence_result = coordinator.persist_and_score_run(
        BenchmarkRunPersistenceRequest(
            benchmark_run_summary=run_summary,
            model_profile_id=seed_ids.model_profile_id,
            hardware_profile_id=seed_ids.hardware_profile_id,
            runtime_profile_id=seed_ids.runtime_profile_id,
            context_profile_id=seed_ids.context_profile_id,
            source_git_commit="coordinator-failed-case",
            run_mode="integration_test",
        ),
        scoring_requests=(),
    )

    benchmark_case_result_id = (
        persistence_result.benchmark_case_result_ids[0]
    )

    persisted_case_result = benchmark_database_session.get(
        BenchmarkCaseResult,
        benchmark_case_result_id,
    )

    assert persisted_case_result is not None
    assert persisted_case_result.result_status == "failed"
    assert persisted_case_result.error_type == "RuntimeError"
    assert persisted_case_result.error_message == (
        "Synthetic coordinator inference failure."
    )

    assert persisted_case_result.normalized_quality_score is None
    assert persisted_case_result.passed is None

    persisted_quality_scores = benchmark_database_session.scalars(
        select(BenchmarkQualityScore).where(
            BenchmarkQualityScore.benchmark_case_result_id
            == benchmark_case_result_id
        )
    ).all()

    assert persisted_quality_scores == []