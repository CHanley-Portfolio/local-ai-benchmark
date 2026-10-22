"""
Tests for the Benchmark Service FastAPI adapter.

These tests verify HTTP behavior without duplicating benchmark application
logic inside route handlers.
"""

from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from local_ai_benchmark.api import create_app
from local_ai_benchmark.api.dependencies import get_database_session
from local_ai_benchmark.persistence.seeding import seed_benchmark_test_data


def test_health_endpoint_returns_api_status() -> None:
    """
    Verify the Benchmark Service exposes a machine-readable health endpoint.
    """

    benchmark_api = create_app()

    with TestClient(benchmark_api) as api_client:
        response = api_client.get(
            "/health"
        )

    assert response.status_code == 200

    assert response.json() == {
        "service": "local-ai-benchmark",
        "status": "ok",
    }


def test_health_endpoint_does_not_require_database_credentials(
    monkeypatch,
) -> None:
    """
    Verify basic API availability is independent of PostgreSQL readiness.

    A missing database password must not prevent the FastAPI process or basic
    health route from starting. Database readiness will be tested separately.
    """

    monkeypatch.delenv(
        "LOCAL_AI_BENCHMARK_DB_PASSWORD",
        raising=False,
    )

    benchmark_api = create_app()

    with TestClient(benchmark_api) as api_client:
        response = api_client.get(
            "/health"
        )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_benchmark_suites_endpoint_reads_persisted_data(
    benchmark_database_session: Session,
) -> None:
    """
    Verify the API exposes persisted suite data through the application query layer.
    """

    seed_ids = seed_benchmark_test_data(
        benchmark_database_session
    )

    benchmark_api = create_app()

    def override_database_session() -> Generator[Session, None, None]:
        yield benchmark_database_session

    benchmark_api.dependency_overrides[
        get_database_session
    ] = override_database_session

    with TestClient(benchmark_api) as api_client:
        response = api_client.get(
            "/benchmark-suites",
            params={
                "suite_name": "local_ai_benchmark_seed",
            },
        )

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["total_count"] == 1
    assert response_data["limit"] == 50
    assert response_data["offset"] == 0

    assert len(response_data["items"]) == 1

    benchmark_suite = response_data["items"][0]

    assert benchmark_suite["benchmark_suite_id"] == (
        seed_ids.benchmark_suite_id
    )
    assert benchmark_suite["suite_name"] == (
        "local_ai_benchmark_seed"
    )
    assert benchmark_suite["suite_version"] == 1
    assert benchmark_suite["description"] == (
        "Synthetic integration-test benchmark suite."
    )


def test_benchmark_suites_endpoint_validates_pagination() -> None:
    """
    Verify invalid pagination is rejected before database access.
    """

    benchmark_api = create_app()

    with TestClient(benchmark_api) as api_client:
        response = api_client.get(
            "/benchmark-suites",
            params={
                "limit": 0,
            },
        )

    assert response.status_code == 422