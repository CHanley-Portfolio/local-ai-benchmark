"""
Persistence adapter for BenchmarkRunner execution summaries.

This module translates immutable execution evidence into SQLAlchemy ORM rows.
It does not execute benchmarks and it does not perform quality scoring.
"""

from decimal import Decimal

from sqlalchemy.orm import Session

from local_ai_benchmark.execution import BenchmarkCaseExecution

from .data import (
    BenchmarkRunPersistenceRequest,
    BenchmarkRunPersistenceResult,
)
from .models import (
    BenchmarkCaseResult,
    BenchmarkPerformanceMetric,
    BenchmarkRun,
)


_NANOSECONDS_PER_SECOND = Decimal("1000000000")


def _calculate_tokens_per_second(
    *,
    token_count: int | None,
    duration_ns: int | None,
) -> Decimal | None:
    """
    Convert token count and nanosecond duration into tokens per second.
    """

    if token_count is None or duration_ns is None or duration_ns <= 0:
        return None

    return (Decimal(token_count) * _NANOSECONDS_PER_SECOND) / Decimal(duration_ns)


class BenchmarkRunRecorder:
    """
    Persist BenchmarkRunner execution summaries into benchmark history.

    Transaction ownership deliberately remains with the caller. persist_run()
    adds and flushes ORM rows so primary keys are available, but it does not
    commit. A CLI, API, scheduled job, or test controls the transaction.
    """

    def __init__(self, database_session: Session) -> None:
        """
        Create a recorder bound to an existing SQLAlchemy session.
        """

        self._database_session = database_session

    def persist_run(
        self,
        persistence_request: BenchmarkRunPersistenceRequest,
    ) -> BenchmarkRunPersistenceResult:
        """
        Persist one completed benchmark-suite execution.

        Successful case executions create both BenchmarkCaseResult and
        BenchmarkPerformanceMetric rows.

        Failed case executions still create BenchmarkCaseResult rows with
        preserved diagnostics, but no performance row is fabricated when the
        inference backend produced no result.

        Quality score fields remain unset because scoring is a separate stage.
        """

        benchmark_run_summary = persistence_request.benchmark_run_summary

        benchmark_run = BenchmarkRun(
            benchmark_suite_id=benchmark_run_summary.benchmark_suite_id,
            model_profile_id=persistence_request.model_profile_id,
            hardware_profile_id=persistence_request.hardware_profile_id,
            runtime_profile_id=persistence_request.runtime_profile_id,
            context_profile_id=persistence_request.context_profile_id,
            source_git_commit=persistence_request.source_git_commit,
            run_mode=persistence_request.run_mode,
            status=benchmark_run_summary.status,
            started_at=benchmark_run_summary.started_at,
            completed_at=benchmark_run_summary.completed_at,
            notes=persistence_request.notes,
        )

        self._database_session.add(benchmark_run)
        self._database_session.flush()

        benchmark_case_result_ids: list[int] = []

        for case_execution in benchmark_run_summary.case_executions:
            benchmark_case_result = self._persist_case_execution(
                benchmark_run_id=benchmark_run.benchmark_run_id,
                case_execution=case_execution,
            )

            benchmark_case_result_ids.append(
                benchmark_case_result.benchmark_case_result_id
            )

        return BenchmarkRunPersistenceResult(
            benchmark_run_id=benchmark_run.benchmark_run_id,
            benchmark_case_result_ids=tuple(benchmark_case_result_ids),
        )

    def _persist_case_execution(
        self,
        *,
        benchmark_run_id: int,
        case_execution: BenchmarkCaseExecution,
    ) -> BenchmarkCaseResult:
        """
        Persist one case execution and any available performance telemetry.
        """

        inference_result = case_execution.inference_result

        benchmark_case_result = BenchmarkCaseResult(
            benchmark_run_id=benchmark_run_id,
            benchmark_case_id=case_execution.benchmark_case_id,
            result_status=case_execution.status,
            raw_model_response=(
                inference_result.response_text if inference_result is not None else None
            ),
            normalized_quality_score=None,
            passed=None,
            diagnostic_text=None,
            error_type=case_execution.error_type,
            error_message=case_execution.error_message,
            started_at=case_execution.started_at,
            completed_at=case_execution.completed_at,
        )

        self._database_session.add(benchmark_case_result)
        self._database_session.flush()

        if inference_result is not None:
            performance_metric = BenchmarkPerformanceMetric(
                benchmark_case_result_id=(
                    benchmark_case_result.benchmark_case_result_id
                ),
                total_duration_ns=inference_result.total_duration_ns,
                model_load_duration_ns=inference_result.model_load_duration_ns,
                prompt_token_count=inference_result.prompt_token_count,
                prompt_eval_duration_ns=inference_result.prompt_eval_duration_ns,
                prompt_tokens_per_second=_calculate_tokens_per_second(
                    token_count=inference_result.prompt_token_count,
                    duration_ns=inference_result.prompt_eval_duration_ns,
                ),
                output_token_count=inference_result.output_token_count,
                output_eval_duration_ns=inference_result.output_eval_duration_ns,
                output_tokens_per_second=_calculate_tokens_per_second(
                    token_count=inference_result.output_token_count,
                    duration_ns=inference_result.output_eval_duration_ns,
                ),
                backend_metrics=inference_result.backend_metrics,
            )

            self._database_session.add(performance_metric)
            self._database_session.flush()

        return benchmark_case_result
