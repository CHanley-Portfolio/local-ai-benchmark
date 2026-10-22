"""
Dependency providers used by the Benchmark Service HTTP API.
"""

from .database import (
    close_database_resources as close_database_resources,
)
from .database import (
    get_database_session as get_database_session,
)

__all__ = [
    "close_database_resources",
    "get_database_session",
]