"""
Allow the Benchmark Service CLI to run with ``python -m local_ai_benchmark``.
"""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())