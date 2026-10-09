"""
Persistence adapter for benchmark quality-scoring evidence.

BenchmarkScoreRecorder records aggregate case quality and criterion-level
scoring evidence after benchmark execution has already been persisted.

It does not perform scoring itself.
"""

from sqlalchemy.orm import Session

from .data import BenchmarkCaseScorePersistence
from .models import (
    BenchmarkCaseResult,
    BenchmarkQualityScore,
)


class BenchmarkScoreRecorder:
    """
    Persist BenchmarkCaseScore results into benchmark history.

    The recorder is intentionally separate from BenchmarkRunRecorder.

    BenchmarkRunRecorder owns execution evidence such as model output,
    timestamps, failures, and performance telemetry.

    BenchmarkScoreRecorder owns quality evidence produced by the scoring layer.

    Keeping these responsibilities separate mirrors the database design where
    quality measurements and runtime measurements are distinct concerns.
    """

    def __init__(
        self,
        database_session: Session,
    ) -> None:
        """
        Create a score recorder using an existing SQLAlchemy session.

        Args:
            database_session:
                Active Benchmark Service database session.

                Transaction ownership remains with the caller. This recorder
                flushes changes but does not commit them.
        """

        self._database_session = database_session

    def persist_case_score(
        self,
        score_persistence: BenchmarkCaseScorePersistence,
    ) -> None:
        """
        Persist aggregate and criterion-level quality evidence.

        Args:
            score_persistence:
                Association between an existing BenchmarkCaseResult record and
                its BenchmarkCaseScore.

        Raises:
            ValueError:
                Raised when the requested BenchmarkCaseResult does not exist or
                when the score belongs to a different benchmark case.
        """

        benchmark_case_result = self._database_session.get(
            BenchmarkCaseResult,
            score_persistence.benchmark_case_result_id,
        )

        if benchmark_case_result is None:
            raise ValueError(
                "Cannot persist benchmark score because "
                "BenchmarkCaseResult "
                f"{score_persistence.benchmark_case_result_id} does not exist."
            )

        benchmark_case_score = score_persistence.benchmark_case_score

        if (
            benchmark_case_result.benchmark_case_id
            != benchmark_case_score.benchmark_case_id
        ):
            raise ValueError(
                "Benchmark score case ID does not match the persisted "
                "BenchmarkCaseResult case ID."
            )

        # Store the aggregate quality result directly on the case-result row.
        benchmark_case_result.normalized_quality_score = (
            benchmark_case_score.normalized_quality_score
        )
        benchmark_case_result.passed = benchmark_case_score.passed
        benchmark_case_result.diagnostic_text = (
            benchmark_case_score.diagnostic_text
        )

        # Preserve every criterion that contributed to the aggregate score.
        for criterion_score in benchmark_case_score.criterion_scores:
            benchmark_quality_score = BenchmarkQualityScore(
                benchmark_case_result_id=(
                    benchmark_case_result.benchmark_case_result_id
                ),
                criterion_name=criterion_score.criterion_name,
                raw_score=criterion_score.raw_score,
                max_score=criterion_score.max_score,
                normalized_score=criterion_score.normalized_score,
                passed=criterion_score.passed,
                scorer_type=criterion_score.scorer_type,
                scorer_version=criterion_score.scorer_version,
                details=criterion_score.details,
            )

            self._database_session.add(benchmark_quality_score)

        self._database_session.flush()