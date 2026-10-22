"""
Read-only application queries fro persisted benchmark suites.

HTTP routes and other adapters should use this service rather than issuing
SQLAlchemy queries directly.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from local_ai_benchmark.persistence.models import BenchmarkSuite

from .data import BenchmarkSuitePage, BenchmarkSuiteSummary


class BenchmarkSuiteQueryService:
    """
    Query persisted benchmark-suite definitions.

    The service owns database query behavior while returning application-layer
    data contracts rather than SQLAlchemy ORM objects.
    """

    def __init__(self, database_session: Session) -> None:
        """
        Create teh benchmark-suite query service.

        Args:
            database_session:
                Active SQLAlchemy session used for read-only suite queries.
        """

        self._database_session = database_session

    def list_suites(self, *, limit: int = 50, offset: int = 0, suite_name: str | None = None) -> BenchmarkSuitePage:
        """
        Return one ordered page of persisted benchmark suites.

        Args:
            limit:
                Maximum number of suite records returned.

            offset:
                Number of matching suite records skipped before the page.

            suite_name:
                Optional case-insensitive partial suite-name filter.

        Returns:
            BenchmarkSuitePage:
                Immutable suite summaries and the complete filtered rown count.

        Raises:
            ValueError:
                Raised when pagination values are outside supported bounds.
        """

        if limit < 1 or limit > 100:
            raise ValueError("Benchmark suite query limit must be between 1 and 100.")

        if offset < 0:
            raise ValueError("Benchmark suite query offset must not be negative.")

        normalized_suite_name = (
            suite_name.strip()
            if suite_name is not None
            else None
        )

        if normalized_suite_name == "":
            normalized_suite_name = None

        count_statement = select(func.count()).select_from(BenchmarkSuite)

        suite_statement = select(BenchmarkSuite)

        if normalized_suite_name is not None:
            suite_filter = BenchmarkSuite.suite_name.ilike(f"%{normalized_suite_name}%")
            count_statement = count_statement.where(suite_filter)
            suite_statement = suite_statement.where(suite_filter)

        total_count = self._database_session.scalar(count_statement)

        benchmark_suites = self._database_session.scalars(
            suite_statement
            .order_by(
                BenchmarkSuite.suite_name.asc(),
                BenchmarkSuite.suite_version.desc(),
                BenchmarkSuite.benchmark_suite_id.asc(),
            )
            .limit(limit)
            .offset(offset)
        ).all()

        suite_summaries = tuple(
            BenchmarkSuiteSummary(
                benchmark_suite_id=benchmark_suite.benchmark_suite_id,
                suite_name=benchmark_suite.suite_name,
                suite_version=benchmark_suite.suite_version,
                description=benchmark_suite.description,
                created_at=benchmark_suite.created_at,
            )
            for benchmark_suite in benchmark_suites
        )

        return BenchmarkSuitePage(
            items=suite_summaries,
            total_count=int(total_count or 0)
        )