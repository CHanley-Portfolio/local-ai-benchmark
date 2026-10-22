"""
HTTP API adapter for the Local AI Benchmark Service.
"""

from .app import create_app as create_app

__all__ = [
    "create_app",
]