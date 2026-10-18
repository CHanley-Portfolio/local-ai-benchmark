"""
Unit tests for the standalone Benchmark Service CLI.
"""

from local_ai_benchmark.cli import build_argument_parser


def test_cli_parses_run_suite_command() -> None:
    """
    Verify the independent run-suite action exposes required identifiers.
    """

    parser = build_argument_parser()

    arguments = parser.parse_args(
        [
            "run-suite",
            "--suite-id",
            "10",
            "--model-profile-id",
            "20",
            "--hardware-profile-id",
            "30",
            "--runtime-profile-id",
            "40",
            "--context-profile-id",
            "50",
            "--source-git-commit",
            "abc123",
        ]
    )

    assert arguments.command == "run-suite"
    assert arguments.suite_id == 10
    assert arguments.model_profile_id == 20
    assert arguments.hardware_profile_id == 30
    assert arguments.runtime_profile_id == 40
    assert arguments.context_profile_id == 50
    assert arguments.source_git_commit == "abc123"
    assert arguments.run_mode == "manual_cli"