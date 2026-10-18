"""
Build application execution requests from persisted benchmark configuration.

BenchmarkExecutionRequestBuilder translates PostgreSQL-backed benchmark suite, case,
model-profile, and environment configuration into the backend-dependent contracts consumed by BenchmarkExecutionService.

The builder does not execute inference, score results, persist benchmark runs,
or commmit database transactions.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from local_ai_benchmark.application.data import BenchmarkCasePlan, BenchmarkExecutionRequest
from local_ai_benchmark.execution import BenchmarkCaseRequest
from local_ai_benchmark.inference import InferenceRequest
from local_ai_benchmark.persistence.models import (
    BenchmarkCase,
    BenchmarkSuite,
    BenchmarkSuiteCase,
    ContextProfile,
    HardwareProfile,
    ModelProfile,
    RuntimeProfile,
)


class BenchmarkExecutionRequestBuilder:
    """
    Build one executable benchmark request from persisted configuration.

    This class bridges configuration stored in PostgreSQL with the normalized 
    application contracts used by BenchmarkExecutionService.
    """

    def __init__(self, database_session: Session) -> None:
        """
        Create request builder.

        Args:
            database_session:
                Active SQLAlchemy session used to read benchmark configuration.
        """

        self._database_session = database_session
    
    def build(
        self,
        *,
        benchmark_suite_id: int,
        model_profile_id: int,
        hardware_profile_id: int,
        runtime_profile_id: int,
        context_profile_id: int | None,
        source_git_commit: str | None,
        run_mode: str,
        notes: str | None = None,
    ) -> BenchmarkExecutionRequest:
        """
        Build one complete BenchmarkExecutionRequest.

        Raises:
            ValueError:
                raised when requied configuration does not exist, the suite is
                empty, or the suite contains an execution type that is not yet supported
                by the standalone Benchmark Service.
        """

        benchmark_suite = self._database_session.get(BenchmarkSuite, benchmark_suite_id)

        if benchmark_suite is None:
            raise ValueError(
                f"Benchmark suite {benchmark_suite_id} does not exist."
            )

        model_profile = self._database_session.get(ModelProfile, model_profile_id)

        if model_profile is None:
            raise ValueError(
                f"Model profile {model_profile_id} does not exist."
            )

        hardware_profile = self._database_session.get(HardwareProfile, hardware_profile_id)

        if hardware_profile is None:
            raise ValueError(
                f"Hardware profile {hardware_profile_id} does not exist."
            )

        runtime_profile = self._database_session.get(RuntimeProfile, runtime_profile_id)

        if runtime_profile is None:
            raise ValueError(
                f"Runtime profile {runtime_profile_id} does not exist."
            )

        if context_profile_id is not None:
            context_profile = self._database_session.get(ContextProfile, context_profile_id)

            if context_profile is None:
                raise ValueError(
                    f"Context profile {context_profile_id} does not exist."
                )

        benchmark_cases = self._database_session.scalars(
            select(BenchmarkCase)
            .join(
                BenchmarkSuiteCase,
                BenchmarkSuiteCase.benchmark_case_id == BenchmarkCase.benchmark_case_id,
            )
            .where(
                BenchmarkSuiteCase.benchmark_suite_id == benchmark_suite_id
            )
            .order_by(
                BenchmarkSuiteCase.execution_order.asc().nulls_last(),
                BenchmarkSuiteCase.benchmark_case_id.asc(),
            )
        ).all()

        if not benchmark_cases:
            raise ValueError(
                f"Benchmark suite {benchmark_suite_id} contains no cases."
            )

        backend_model_name = (
            model_profile.model_variant.backend_model_name
        )

        case_plans: list[BenchmarkCasePlan] = []

        for benchmark_case in benchmark_cases:
            case_plans.append(
                self._build_case_plan(
                    benchmark_case=benchmark_case,
                    backend_model_name=backend_model_name,
                    model_profile=model_profile,
                )
            )

        return BenchmarkExecutionRequest(
            benchmark_suite_id=benchmark_suite_id,
            case_plans=tuple(case_plans),
            model_profile_id=model_profile_id,
            hardware_profile_id=hardware_profile_id,
            runtime_profile_id=runtime_profile_id,
            context_profile_id=context_profile_id,
            source_git_commit=source_git_commit,
            run_mode=run_mode,
            notes=notes,    
        )

    @staticmethod
    def _build_case_plan(*, benchmark_case: BenchmarkCase, backend_model_name: str, model_profile: ModelProfile) -> BenchmarkCasePlan:
        """
        Convert one persisted BenchmarkCase into an application case plan.
        """

        # Router-arget benchmarks will eventually execute through a dedicated
        # adapter/API boundary. the Benchmark Service must not import router
        # implementation code directly.
        if benchmark_case.evaluation_target != "model":
            raise ValueError(
                "Persisted benchmark case "
                f"{benchmark_case.external_case_id} uses unsupported "
                f"evaluation_target='{benchmark_case.evaluation_target}'."
            )

        # Context-fixture loading is intentionally rejected until the context
        # fixture pipeline is implemented. Silently ignoring the fixture would
        # produce an invalid benchmark result.
        if benchmark_case.context_fixture is not None:
            raise ValueError(
                "Persisted benchmark case "
                f"{benchmark_case.external_case_id} requires context fixture "
                f"'{benchmark_case.context_fixture}', but context fixture "
                "loading is not implemented yet."
            )

        expected_criteria = (
            BenchmarkExecutionRequestBuilder._normalize_expected_criteria(
                benchmark_case.expected_criteria
            )
        )

        inference_request = InferenceRequest(
            model_name=backend_model_name,
            user_message=benchmark_case.prompt_text,
            thinking_enabled=(
                model_profile.reasoning_enabled is True
            ),
            temperature=model_profile.temperature,
            top_p=model_profile.top_p,
            seed=model_profile.seed,
            max_output_tokens=model_profile.max_output_tokens,
            backend_options=(
                dict(model_profile.backend_options)
                if model_profile.backend_options is not None
                else None
            ),
        )

        return BenchmarkCasePlan(
            case_request=BenchmarkCaseRequest(
                benchmark_case_id=benchmark_case.benchmark_case_id,
                inference_request=inference_request,
            ),
            evaluation_target=benchmark_case.evaluation_target,
            scoring_method=benchmark_case.scoring_method,
            expected_answer=benchmark_case.expected_answer,
            expected_route_mode=benchmark_case.expected_route_mode,
            expected_criteria=expected_criteria,
        )

    @staticmethod
    def _normalize_expected_criteria(
        expected_criteria: dict[str, Any] | list[Any] | None,
    ) -> tuple[str, ...]:
        """
        Convert persisted JSONB scoring criteria into an immutable tuple.

        The current scoring contract requires an ordered sequence of strings.
        Unexpected JSON structures are rejected instead of silently coerced.
        """

        if expected_criteria is None:
            return ()

        if not isinstance(expected_criteria, list):
            raise ValueError(
                "Benchmark expected_criteria must be a JSON array."
            )

        if not all(
            isinstance(criterion, str)
            for criterion in expected_criteria
        ):
            raise ValueError(
                "Every benchmark scoring criterion must be a string."
            )

        return tuple(expected_criteria)

