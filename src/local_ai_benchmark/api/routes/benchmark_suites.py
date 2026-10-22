"""
HTTP routes for persisted benchmark-suite definitions.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from local_ai_benchmark.api.dependencies import get_database_session
from local_ai_benchmark.api.schemas import (
    BenchmarkSuiteListResponse,
    BenchmarkSuiteResponse,
)
from local_ai_benchmark.application.benchmark_suite_query_service import (
    BenchmarkSuiteQueryService,
)

router = APIRouter(
    prefix="/benchmark-suites",
    tags=["Benchmark Suites"],
)


@router.get(
    "",
    response_model=BenchmarkSuiteListResponse,
    summary="List benchmark suites",
)
def list_benchmark_suites(
    database_session: Annotated[Session, Depends(get_database_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    suite_name: Annotated[str | None, Query(min_length=1)] = None
) -> BenchmarkSuiteListResponse:
    """
    Return persisted benchmark suites with pagination and optional name filtering.

    SQLAlchemy query remains inside BenchmarkSuiteQueryService.
    """

    query_service = BenchmarkSuiteQueryService(database_session)

    suite_page = query_service.list_suites(
        limit=limit,
        offset=offset,
        suite_name=suite_name,
    )

    return BenchmarkSuiteListResponse(
        items=[
            BenchmarkSuiteResponse(
                benchmark_suite_id=summary.benchmark_suite_id,
                suite_name=summary.suite_name,
                suite_version=summary.suite_version,
                description=summary.description,
                created_at=summary.created_at,
            )
            for summary in suite_page.items
        ],
        total_count=suite_page.total_count,
        limit=limit,
        offset=offset,
    )