"""
Top-Level application service for executing benchmark suites.

BenchmarkExecutionService coordinates teh complete benchmark lifecycle:

1. validate the benchmark execution request;
2. execute the suite through BenchmarkRunner;
3. convert successful execution evidence into scoring requests;
4. persist and score the run through BenchmarkRunCoordinator;
5. commit the database transaction;
6. return a machin-readable BenchmarkExecutionResult.

If persistence or scoring fails, the database transaction is rolled back.
"""

from sqlalchemy.orm import Session

from local_ai_benchmark.execution import BenchmarkRunner
from local_ai_benchmark.persistence import BenchmarkRunPersistenceRequest
from local_ai_benchmark.scoring import BenchmarkScoringRequest

from .benchmark_run_coordinator import BenchmarkRunCoordinator
from .data import BenchmarkCasePlan, BenchmarkExecutionRequest, BenchmarkExecutionResult


class BenchmarkExecutionService:
    """
    Execute, score and persist one benchmark suite as one application workflow.

    Lower-level responsibilities remain delegated to their existing components.

    BenchmarkRunner:
        Performs inference execution.

    BenchmarkRunCoordinator:
        Coordinates persistenceand quality scoring.

    BenchmarkExecutionService:
        Owns the complete application transaction and exposes one operation that future CLI/API callers can invoke.
    """

    def __init__(self, database_session: Session, benchmark_runner: BenchmarkRunner, benchmark_run_coordinator: BenchmarkRunCoordinator) -> None:
        """
        Create the benchmark execution service.

        Args:
            database_session:
                SQLAlchemy session whose transaction will be committed or rolled back by this service.

            benchmark_runner:
                Runner responsible for executing benchmark inference.

            benchmark_run_coordinator:
                Coordinator responsible for persisting and scoring completed benchmark execution evidence.
        """

        self._database_session = database_session
        self._benchmark_runner = benchmark_runner
        self._benchmark_run_coordinator = benchmark_run_coordinator

    async def execute(self, execution_request: BenchmarkExecutionRequest) -> BenchmarkExecutionResult:
        """
        Execute, score, and persist one benchmark suite.

        Args:
            execution_request:
                Complete application-level description of the benchmark run.

        Returns:
            BenchmarkExecutionResult:
                Machine-readable execution evidence plus durable database IDs.

        Raises:
            ValueError:
                Raised for invalid benchmark case-plan configuration.

            Exception:
                Backend, scoring, or persistence failures propagate after the
                database transaction is rolled back.

        Transaction behavior:
            Successful operations are committed once the entire workflow
            completes.

            If scoring or persistence fails after database rows have been
            flushed, rollback removes the partial run.
        """

        self._validate_case_plans(execution_request.case_plans)

        case_requests = tuple(
            case_plan.case_request 
            for case_plan in execution_request.case_plans
        )

        try:
            benchmark_run_summary = await self._benchmark_runner.execute_suite(
                benchmark_suite_id=execution_request.benchmark_suite_id,
                case_requests=case_requests,
            )

            scoring_requests = self._build_scoring_requests(
                case_plans=execution_request.case_plans,
                benchmark_run_summary=benchmark_run_summary,
            )

            persistence_result = (
                self._benchmark_run_coordinator.persist_and_score_run(
                    BenchmarkRunPersistenceRequest(
                        benchmark_run_summary=benchmark_run_summary,
                        model_profile_id=execution_request.model_profile_id,
                        hardware_profile_id=execution_request.hardware_profile_id,
                        runtime_profile_id=execution_request.runtime_profile_id,
                        context_profile_id=execution_request.context_profile_id,
                        source_git_commit=execution_request.source_git_commit,
                        run_mode=execution_request.run_mode,
                        notes=execution_request.notes,
                    ),
                    scoring_requests=scoring_requests,
                )
            )

            self._database_session.commit()

        except Exception:
            self._database_session.rollback()
            raise

        return BenchmarkExecutionResult(
            benchmark_run_id=persistence_result.benchmark_run_id,
            benchmark_case_result_ids=persistence_result.benchmark_case_result_ids,
            benchmark_run_summary=benchmark_run_summary,
        )

    @staticmethod
    def _validate_case_plans(case_plans: tuple[BenchmarkCasePlan,...]) -> None:
        """
        Validate benchmark case plans before inference begins.

        Raises:
            ValueError:
                raised when the suite contains no cases or contains duplicate
                persistent benchmark-case identifiers.
        """

        if not case_plans:
            raise ValueError(
                "Benchmark execution requires at least one case plan."
            )

        benchmark_case_ids: set[int] = set()

        for case_plan in case_plans:
            benchmark_case_id = case_plan.case_request.benchmark_case_id

            if benchmark_case_id in benchmark_case_ids:
                raise ValueError("Duplicate benchmark case plan for benchmark case" f"{benchmark_case_id}")

            benchmark_case_ids.add(benchmark_case_id)

    @staticmethod
    def _build_scoring_requests(*,case_plans: tuple[BenchmarkCasePlan, ...], benchmark_run_summary) -> tuple[BenchmarkScoringRequest, ...]:
        """
        Convert completed execution evidence into scorer-ready requests.

        Failed inference cases intentionally produce no scoring request because no successful model responce exists to evaluate.

        Router-target execusion will be added through its own execution adapter. 
        The Benchmark Service must not import local_ai_router directly.
        """

        case_plans_by_id = {
            case_plan.case_request.benchmark_case_id: case_plan 
            for case_plan in case_plans
        }

        scoring_requests: list[BenchmarkScoringRequest] = []

        for case_execution in benchmark_run_summary.case_executions:
            if case_execution.status != "completed":
                continue

            case_plan = case_plans_by_id[
                case_execution.benchmark_case_id
            ]

            if case_plan.evaluation_target != "model":
                raise ValueError(
                    "BenchmarkExecutionService currently supports completed "
                    "model evaluation targets only. "
                    f"Received evaluation_target="
                    f"'{case_plan.evaluation_target}'."
                )

            if case_execution.inference_result is None:
                raise ValueError(
                    "Completed benchmark case "
                    f"{case_execution.benchmark_case_id} does not contain "
                    "an inference result."
                )

            scoring_requests.append(
                BenchmarkScoringRequest(
                    benchmark_case_id = case_execution.benchmark_case_id,
                    evaluation_target = case_plan.evaluation_target,
                    scoring_method = case_plan.scoring_method,
                    response_text = case_execution.inference_result.response_text,
                    expected_answer = case_plan.expected_answer,
                    expected_route_mode = case_plan.expected_route_mode,
                    expected_criteria = case_plan.expected_criteria,
                )
            )
        
        return tuple(scoring_requests)