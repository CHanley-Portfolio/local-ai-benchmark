"""
Health endpoints for the BEnchmark Service API.
"""

from fastapi import APIRouter

from local_ai_benchmark.api.schemas import HealthResponse

router = APIRouter(tags=["Health"])

@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check Benchmark Service API health",
)

def get_health() -> HealthResponse:
    """
    Return the availability state of the HTTP service itself.

    This route deliberately performs no  PostgreSQL or Ollama access.

    Dependency-specific readines checks will be exposed seperately so clients
    can distinguish an unavailable API process from an unavailable database, 
    inference backend, or other depenedency.
    """

    return HealthResponse(
        service="local-ai-benchmark",
        status="ok",
    )