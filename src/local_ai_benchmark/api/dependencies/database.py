"""
Lazy PostgreSQL session dependency for the Benchmark Service API.

Database infrastructure is initialized only when the database-backed endpoint is actually requested.
Basic API health therefore remains independent of PostgreSQL availability
"""

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from local_ai_benchmark.persistence.database import (
    create_database_engine,
    create_database_session_factory,
)


@lru_cache(maxsize=1)
def _get_database_engine() -> Engine:
    """
    Lazily create and reuse teh Benchmark Service database engine.
    """

    return create_database_engine()


@lru_cache(maxsize=1)
def _get_database_session_factory() -> sessionmaker[Session]:
    """
    Lazily create teh SQLAlchemy session factory used by API requests.
    """

    return create_database_session_factory(_get_database_engine)


def get_database_session() -> Generator[Session, None, None]:
    """
    Provide one SQlAlchemy session for a database-backed HTTP request.

    The session is always closed after request processing. Transaction ownership
    remains with the application service being invoked.
    """

    database_session_factory = _get_database_session_factory()

    with database_session_factory() as database_session:
        yield database_session


def close_database_resources() -> None:
    """
    Dispose lazily-created API database infrastructure during shutdown.
    """

    if _get_database_engine.cache_info().currsize > 0:
        database_engine = _get_database_engine()
        database_engine.dispose()

    _get_database_session_factory.cache_clear()
    _get_database_engine.cache_clear()