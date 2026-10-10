"""
Application-level orchestration for completed benchmark runs.

BenchmarkRunCoordinator connects benchmark execution results, scoring, and 
persistence without moving those responsibilities into one monolithic class. 

Individual components remain responsible for their own domains:
    - BenchmarkRunner: 
        runs the benchmark case and collects the model's response
        and performance data.
    - BenchmarkScorer 
        checks how good or correct the benchmark result is.

    - BenchmarkRunRecorder 
        saves the benchmark run, model response, errors,
        timing data, and other performance information to the database.

    - BenchmarkScoreRecorder 
        saves the quality score and detailed scoring
        information to the database.

    - BenchmarkRunCoordinator 
        connects all of those steps together in the correct
        order without taking over their individual responsibilities.
"""

from sqlalchemy.orm import Session

from local_ai_benchmark.persistence import (
    BenchmarkRunPersistenceRequest,
    BenchmarkRunRecorder,
    BenchmarkScoreRecorder,
    BenchmarkCaseScorePersistence,
    BenchmarkRunPersistenceResult,
)
from local_ai_benchmark.scoring import BenchmarkScorerRegistry, BenchmarkScoringRequest

class BenchmarkRunCoordinator:
    """
    Coordinate persistence and scoring for one completed benchmark run.

    This class belongs to the application layer because it coordinates several
    lower-level services but does not own their implementation details.

    The coordinator deliberately does not commit database transactions.
    Transaction ownership remains with the caller so the entire benchmark
    operation can later be committed or rolled back atomically.
    """

    def __init__(
        self,
        database_session: Session,
        scorer_registry: BenchmarkScorerRegistry,
    ) -> None:
        """
        Create a new BenchmarkRunCoordinator.

        Args:
            database_session: 
                The SQLAlchemy session to use for database operations by the persistence layer.
            scorer_registry:
                Registry used to resolve each benchmark case's configured scoring implementation.             
        """

        self._database_session = database_session
        self._scorer_registry = scorer_registry

        self._run_recorder = BenchmarkRunRecorder(database_session)
        self._score_recorder = BenchmarkScoreRecorder(database_session)


    def persist_and_score_run(
        self,
        persistence_request: BenchmarkRunPersistenceRequest,
        scoring_requests: tuple[BenchmarkScoringRequest, ...],
    ) -> BenchmarkRunPersistenceResult:
        """
        Persist execution evidence and score every completed benchmark case.

        Args:
            persistence_request:
                Run summary plus model, hardware, runtime, context, and source
                metadata required for durable benchmark history.

            scoring_requests:
                Normalized scoring requirements for completed benchmark cases.

        Returns:
            BenchmarkRunPersistenceResult:
                Durable benchmark-run identifier and ordered case-result IDs.

        Raises:
            ValueError:
                Raised when scoring requests contain duplicate benchmark-case
                IDs or when a completed case does not have a scoring request.

        Notes:
            Failed inference cases are persisted by BenchmarkRunRecorder but are
            not quality scored because there is no completed model/router result
            to evaluate.

            Any exception propagates to the caller. Because neither recorder
            commits, the caller can roll back the entire operation.
        """

        scoring_requests_by_case_id = self._build_scoring_request_lookup(scoring_requests)
        persistence_result = self._run_recorder.persist_run(persistence_request)
        benchmark_run_summary = persistence_request.benchmark_run_summary

        # BenchmarkRunRecorder preserves the runner's case order when it
        # creates BenchmarkCaseResult records. Pairing these sequences allows us 
        # to associate each execution with its database result ID.
        for case_execution, benchmark_case_result_id in zip(
            benchmark_run_summary.case_executions,
            persistence_result.benchmark_case_result_ids,
            strict=True,
        ):
            # Failed inference remains useful benchmark evidence, but it cannot
            # receive a qulity score because there is no successful observed
            # result to evaluate. Skip scoring for failed cases.
            if case_execution.status != "completed":
                continue

            scoring_request = scoring_requests_by_case_id.get(case_execution.benchmark_case_id)

            if scoring_request is None:
                raise ValueError(
                    "Completed benchmark case "
                    f"{case_execution.benchmark_case_id} does not have a "
                    "scoring request."
                )

            benchmark_scorer = self._scorer_registry.get_scorer(scoring_request.scoring_method)

            benchmark_case_score = benchmark_scorer.score(scoring_request)

            self._score_recorder.persist_case_score(
                BenchmarkCaseScorePersistence(
                    benchmark_case_result_id=benchmark_case_result_id,
                    benchmark_case_score=benchmark_case_score,
                )
            )

        return persistence_result

    @staticmethod
    def _build_scoring_request_lookup(
        scoring_requests: tuple[BenchmarkScoringRequest, ...],
    ) -> dict[int, BenchmarkScoringRequest]:
        """
        Index scoring requests by benchmark-case identifier.

        Args:
            scoring_requests:
                Scoring requests supplied for the benchmark run.

        Returns:
            dict[int, BenchmarkScoringRequest]:
                Lookup keyed by benchmark_case_ids.

        Raises:
            ValueError:
                Raised when more than one scoring request targets the same benchmark case ID.
        """

        scoring_requests_by_case_id: dict[int, BenchmarkScoringRequest] = {}

        for scoring_request in scoring_requests:
            benchmark_case_id = scoring_request.benchmark_case_id

            if benchmark_case_id in scoring_requests_by_case_id:
                raise ValueError(
                    "Duplicate scoring request for benchmark case "
                    f"{benchmark_case_id}."
                )

            scoring_requests_by_case_id[benchmark_case_id] = scoring_request

        return scoring_requests_by_case_id