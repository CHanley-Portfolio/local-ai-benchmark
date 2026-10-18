"""
Application-level plan for one benchmark case.

BenchmarkCasePlan combines the execution request for a benchmark case with 
the quality-scoring expectations that should be applied after successful execution.

It deliberately contains no SQLAlchemy ORM objects
"""

from dataclasses import dataclass

from local_ai_benchmark.execution import BenchmarkCaseRequest


@dataclass(frozen=True)
class BenchmarkCasePlan:
    """
    Describe how one benchmark case should be executed and scored.

    Attributes:
        case_request:
            Backend-independant execution request containing the persistent benchmark-case ID 
            and nomalized inference request.

        evaluation_target:
            Component being evaluated, such as 'model or 'router'

        scoring_method:
            Stable scoring method identifier resolved through BenchmarkScoringReqistry.

        expected_answer:
            Optional Deterministic expected answer.

        expected_route_mode:
            Optional expected router mode.

        expected_criteria:
            Ordered quality criteria used by rubric-style scorers.
    """

    case_request: BenchmarkCaseRequest

    evaluation_target: str
    scoring_method: str

    expected_answer: str | None = None
    expected_route_mode: str | None = None
    expected_criteria: tuple[str, ...] = ()