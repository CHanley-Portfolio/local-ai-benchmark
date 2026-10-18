"""
Shared pytest fixtures for the Local AI Benchmark Service test suite.

PostgreSQL integration tests use an outer transaction so test data can never
become permanent benchmark history.

Sessions join that transaction through a SAVEPOINT. This allows application
services to call commit() or rollback() normally while the fixture still owns
the outer transaction used for final cleanup.
"""

import os
from collections.abc import Generator

import pytest
from sqlalchemy.orm import Session

from local_ai_benchmark.config import get_benchmark_database_settings
from local_ai_benchmark.persistence.database import create_database_engine


@pytest.fixture
def benchmark_database_session() -> Generator[Session, None, None]:
    """
    Provide an isolated PostgreSQL session for benchmark integration tests.

    The fixture runs only when:

    - LOCAL_AI_BENCHMARK_DB_PASSWORD is available; and
    - the configured database is local_ai_benchmark_test.

    An outer database transaction protects the physical test database.

    SQLAlchemy's ``create_savepoint`` join mode allows application code to
    commit and roll back its own unit of work without committing the fixture's
    outer transaction.

    The outer transaction is always rolled back when the test finishes.
    """

    if not os.getenv("LOCAL_AI_BENCHMARK_DB_PASSWORD"):
        pytest.skip(
            "PostgreSQL integration test requires "
            "LOCAL_AI_BENCHMARK_DB_PASSWORD."
        )

    database_settings = get_benchmark_database_settings()

    if database_settings.database_name != "local_ai_benchmark_test":
        pytest.skip(
            "PostgreSQL benchmark integration tests may only run against "
            "local_ai_benchmark_test."
        )

    database_engine = create_database_engine(database_settings)

    try:
        with database_engine.connect() as database_connection:
            outer_transaction = database_connection.begin()

            try:
                with Session(
                    bind=database_connection,
                    autoflush=False,
                    expire_on_commit=False,
                    join_transaction_mode="create_savepoint",
                ) as database_session:
                    yield database_session

            finally:
                if outer_transaction.is_active:
                    outer_transaction.rollback()

    finally:
        database_engine.dispose()