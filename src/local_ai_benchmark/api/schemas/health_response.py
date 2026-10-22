"""
API response schema for benchmark Service health checks.
"""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """
    Describe the basic availability state of the Benchmark Service API.

    This endpoint intentionallly reports process/API availability only.
    PostgreSQL, Ollama and other dependency readiness will be represented
    seperately so one unavailable dependency does not make API health ambiguous.
    """

    service: str
    status: Literal["ok"]