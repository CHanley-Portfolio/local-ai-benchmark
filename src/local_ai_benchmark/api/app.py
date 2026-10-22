"""
FastAPI application composition for the Local AI Benchmark Service.

The API layer is an adapter around Benchmark Service application logic.
Benchmark execution, scoring, persistence, and comparison behavior must remain
outside HTTP route handlers.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .dependencies import close_database_resources
from .routes import benchmark_suites_router, health_router


@asynccontextmanager
async def benchmark_api_lifespan(
    _: FastAPI,
) -> AsyncGenerator[None, None]:
    """
    Manage infrastructure owned by the HTTP API process.

    PostgreSQL remains lazily initialized. Shutdown disposes the engine only if
    a database-backed endpoint caused it to be created.
    """

    yield

    close_database_resources()


def create_app() -> FastAPI:
    """
    Create and configure one Benchmark Service FastAPI application.

    Application creation deliberately does not connect to PostgreSQL or require
    an inference backend.
    """

    benchmark_api = FastAPI(
        title="Local AI Benchmark Service",
        description=(
            "API for benchmark definitions, execution, persisted results, "
            "historical comparisons, and reporting."
        ),
        version="0.1.0",
        lifespan=benchmark_api_lifespan,
    )

    benchmark_api.include_router(
        health_router
    )

    benchmark_api.include_router(
        benchmark_suites_router
    )

    return benchmark_api