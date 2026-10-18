"""
Command-Line interface for the standalone Local AI Benchmark Service.

The CLI is intentionally thin. It translates command-line arguments into
application-service calls rather than implementing benchmark logic itself.
"""

import argparse
import asyncio
import json
import os
import sys

from local_ai_benchmark.application.benchmark_execution_request_builder import (
    BenchmarkExecutionRequestBuilder,
)
from local_ai_benchmark.application.benchmark_execution_service import (
    BenchmarkExecutionService,
    BenchmarkRunCoordinator,
)
from local_ai_benchmark.execution import BenchmarkRunner
from local_ai_benchmark.inference import OllamaClient
from local_ai_benchmark.persistence.database import (
    create_database_engine,
    create_database_session_factory,
)
from local_ai_benchmark.scoring import create_default_scorer_registry


def build_argument_parser() -> argparse.ArgumentParser:
    """
    Create the Benchmark Service command-line argument parser.
    """

    parser = argparse.ArgumentParser(
        prog="local-ai-benchmark",
        description=(
            "Execute and persist Local AI Benchmark suites."
        ),
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    run_suite_parser = subparsers.add_parser(
        "run-suite",
        help="Execute one persisted benchmark suite.",
    )

    run_suite_parser.add_argument(
        "--suite-id",
        type=int,
        required=True,
        help="Persistent benchmark suite ID.",
    )

    run_suite_parser.add_argument(
        "--model-profile-id",
        type=int,
        required=True,
        help="Persistent model profile ID.",
    )

    run_suite_parser.add_argument(
        "--hardware-profile-id",
        type=int,
        required=True,
        help="Persistent hardware profile ID.",
    )

    run_suite_parser.add_argument(
        "--runtime-profile-id",
        type=int,
        required=True,
        help="Persistent runtime profile ID.",
    )

    run_suite_parser.add_argument(
        "--context-profile-id",
        type=int,
        default=None,
        help="Optional persistent context profile ID.",
    )

    run_suite_parser.add_argument(
        "--source-git-commit",
        default=None,
        help="Optional source Git commit associated with this run.",
    )

    run_suite_parser.add_argument(
        "--run-mode",
        default="manual_cli",
        help="Benchmark run-mode label.",
    )

    run_suite_parser.add_argument(
        "--notes",
        default=None,
        help="Optional notes stored with the benchmark run.",
    )

    run_suite_parser.add_argument(
        "--ollama-base-url",
        default=os.getenv(
            "LOCAL_AI_BENCHMARK_OLLAMA_BASE_URL",
            "http://127.0.0.1:11434",
        ),
        help="Ollama HTTP base URL.",
    )

    return parser


async def _execute_run_suite_command(
    arguments: argparse.Namespace,
) -> dict[str, object]:
    """
    Execute the run-suite command and return its machine-readable summary.
    """

    database_engine = create_database_engine()

    database_session_factory = create_database_session_factory(
        database_engine
    )

    ollama_client: OllamaClient | None = None

    try:
        with database_session_factory() as database_session:
            request_builder = BenchmarkExecutionRequestBuilder(
                database_session
            )

            execution_request = request_builder.build(
                benchmark_suite_id=arguments.suite_id,
                model_profile_id=arguments.model_profile_id,
                hardware_profile_id=arguments.hardware_profile_id,
                runtime_profile_id=arguments.runtime_profile_id,
                context_profile_id=arguments.context_profile_id,
                source_git_commit=arguments.source_git_commit,
                run_mode=arguments.run_mode,
                notes=arguments.notes,
            )

            ollama_client = OllamaClient(
                arguments.ollama_base_url
            )

            benchmark_runner = BenchmarkRunner(
                ollama_client
            )

            benchmark_run_coordinator = BenchmarkRunCoordinator(
                database_session=database_session,
                scorer_registry=create_default_scorer_registry(),
            )

            benchmark_execution_service = BenchmarkExecutionService(
                database_session=database_session,
                benchmark_runner=benchmark_runner,
                benchmark_run_coordinator=benchmark_run_coordinator,
            )

            execution_result = (
                await benchmark_execution_service.execute(
                    execution_request
                )
            )

            benchmark_run_summary = (
                execution_result.benchmark_run_summary
            )

            return {
                "benchmark_run_id": (
                    execution_result.benchmark_run_id
                ),
                "benchmark_case_result_ids": list(
                    execution_result.benchmark_case_result_ids
                ),
                "status": benchmark_run_summary.status,
                "total_case_count": (
                    benchmark_run_summary.total_case_count
                ),
                "completed_case_count": (
                    benchmark_run_summary.completed_case_count
                ),
                "failed_case_count": (
                    benchmark_run_summary.failed_case_count
                ),
                "started_at": (
                    benchmark_run_summary.started_at.isoformat()
                ),
                "completed_at": (
                    benchmark_run_summary.completed_at.isoformat()
                ),
            }

    finally:
        if ollama_client is not None:
            await ollama_client.close()

        database_engine.dispose()


def main(argv: list[str] | None = None) -> int:
    """
    Run the Benchmark Service CLI.

    Returns:
        int:
            Process exit code. Zero indicates successful execution.
    """

    parser = build_argument_parser()
    arguments = parser.parse_args(argv)

    try:
        if arguments.command == "run-suite":
            result = asyncio.run(
                _execute_run_suite_command(arguments)
            )
        else:
            parser.error(
                f"Unsupported command: {arguments.command}"
            )

    except Exception as exc:
        # Keep the CLI readable. Detailed structured logging can be added
        # during the production-hardening phase.
        print(
            "Benchmark execution failed: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1

    print(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        )
    )

    return 0