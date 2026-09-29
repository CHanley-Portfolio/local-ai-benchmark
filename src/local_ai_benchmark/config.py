"""
Configuration owned by the standalone Local AI Benchmark Service.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class BenchmarkDatabaseSettings:
    """
    PostgreSQL connection settings used by the Benchmark Service.

    Attributes:
        host:
            PostgreSQL hostname or IP address.

        port:
            PostgreSQL TCP port.

        database_name:
            Physical PostgreSQL database containing benchmark persistence.

        username:
            PostgreSQL login role used by the Benchmark Service.

        password:
            Password belonging to the PostgreSQL login role.
    """

    host: str
    port: int
    database_name: str
    username: str
    password: str


def get_benchmark_database_settings() -> BenchmarkDatabaseSettings:
    """
    Load Benchmark Service PostgreSQL settings from environment variables.

    The default database and PostgreSQL role names are owned by the standalone
    Benchmark Service. Environment variables may override those defaults for
    development, testing, CI, or deployment environments.

    Returns:
        BenchmarkDatabaseSettings:
            Immutable Benchmark Service database configuration.

    Raises:
        RuntimeError:
            Raised when the required database password is unavailable.
    """

    database_password = os.getenv("LOCAL_AI_BENCHMARK_DB_PASSWORD")

    if not database_password:
        raise RuntimeError("LOCAL_AI_BENCHMARK_DB_PASSWORD environment variable is required.")

    return BenchmarkDatabaseSettings(
        host=os.getenv(
            "LOCAL_AI_BENCHMARK_DB_HOST",
            "127.0.0.1",
        ),
        port=int(
            os.getenv(
                "LOCAL_AI_BENCHMARK_DB_PORT",
                "5432",
            )
        ),
        # Benchmark Service-owned PostgreSQL database name.
        database_name=os.getenv(
            "LOCAL_AI_BENCHMARK_DB_NAME",
            "local_ai_benchmark_db",
        ),
        # Benchmark Service-owned PostgreSQL login role.
        username=os.getenv(
            "LOCAL_AI_BENCHMARK_DB_USER",
            "local_ai_benchmark_app",
        ),
        password=database_password,
    )
