"""
HTTP response schemas for benchmark-suite queries.
"""

from datetime import datetime

from pydantic import BaseModel


class BenchmarkSuiteResponse(BaseModel):
    """
    Public API representation of one persisted benchmark suite.
    """

    benchmark_suite_id: int
    suite_name: str
    suite_version: int
    description: str | None
    created_at: datetime

class BenchmarkSuiteListResponse(BaseModel):
    """
    Paginated API response containging benchmark-suite summaries.
    """

    items: list[BenchmarkSuiteResponse]
    total_count: int
    limit: int
    offset: int