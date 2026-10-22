"""
HTTP route collections for the Benchmark Service API.
"""

from .benchmark_suites import (
    router as benchmark_suites_router,
)
from .health import router as health_router

__all__ = [
    "benchmark_suites_router",
    "health_router",
]