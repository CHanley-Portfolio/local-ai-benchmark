"""
Unit tests for benchmark context fixture loading.
"""

from pathlib import Path

import pytest

from local_ai_benchmark.fixtures import BenchmarkContextFixtureLoader


def test_context_fixture_loader_reads_utf8_fixture(
    tmp_path: Path,
) -> None:
    """
    Verify a configured benchmark fixture can be loaded exactly.
    """

    fixture_path = tmp_path / "project_context_v1.md"
    fixture_path.write_text(
        "Use PostgreSQL for the application.",
        encoding="utf-8",
    )

    fixture_loader = BenchmarkContextFixtureLoader(
        tmp_path
    )

    fixture_text = fixture_loader.load(
        "project_context_v1.md"
    )

    assert fixture_text == (
        "Use PostgreSQL for the application."
    )


def test_context_fixture_loader_rejects_missing_fixture(
    tmp_path: Path,
) -> None:
    """
    Verify missing fixture names fail explicitly.
    """

    fixture_loader = BenchmarkContextFixtureLoader(
        tmp_path
    )

    with pytest.raises(
        FileNotFoundError,
        match="does not exist",
    ):
        fixture_loader.load(
            "missing_context_v1.md"
        )


def test_context_fixture_loader_rejects_path_escape(
    tmp_path: Path,
) -> None:
    """
    Verify fixture names cannot escape the configured fixture directory.
    """

    fixture_loader = BenchmarkContextFixtureLoader(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="configured fixture directory",
    ):
        fixture_loader.load(
            "../outside.md"
        )