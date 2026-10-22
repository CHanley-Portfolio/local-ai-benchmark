"""
Application-layer summary of one persisted benchmark suite.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class BenchmarkSuiteSummary:
    """
    Represents one versioned benchmark suite for read-only application quiries.

    this contract prevents API adapters from returning SQLAlchemy ORM objects directly.
    """

    benchmark_suite_id: int
    suite_name: str
    suite_version: int
    description: str | None
    created_at: datetime
    