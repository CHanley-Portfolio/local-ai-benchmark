"""
Tests for benchmark scorer registration and resolution.

These tests ensure benchmark orchestration can resolve scoring implementations
without knowing concrete scorer classes.
"""

import pytest

from local_ai_benchmark.scoring import (
    BenchmarkScorer,
    BenchmarkScorerRegistry,
    ExactScorer,
    create_default_scorer_registry,
)


def test_scorer_registry_returns_registered_scorer() -> None:
    """
    Verify a scoring method resolves to its configured implementation.
    """

    exact_scorer = ExactScorer()

    scorer_registry = BenchmarkScorerRegistry(
        {
            "exact": exact_scorer,
        }
    )

    resolved_scorer = scorer_registry.get_scorer("exact")

    assert resolved_scorer is exact_scorer
    assert isinstance(resolved_scorer, BenchmarkScorer)


def test_default_scorer_registry_contains_exact_scorer() -> None:
    """
    Verify the production scorer configuration currently supports exact scoring.
    """

    scorer_registry = create_default_scorer_registry()

    resolved_scorer = scorer_registry.get_scorer("exact")

    assert isinstance(resolved_scorer, ExactScorer)


def test_scorer_registry_rejects_unknown_scoring_method() -> None:
    """
    Verify unsupported scoring methods fail explicitly.

    Silently choosing another scorer would make benchmark results invalid, so
    unsupported methods must produce a clear configuration error.
    """

    scorer_registry = create_default_scorer_registry()

    with pytest.raises(
        ValueError,
        match="No benchmark scorer is registered",
    ):
        scorer_registry.get_scorer("rubric")


def test_scorer_registry_rejects_blank_registration_name() -> None:
    """
    Verify a scorer cannot be registered under an empty identifier.
    """

    with pytest.raises(
        ValueError,
        match="cannot contain a blank",
    ):
        BenchmarkScorerRegistry(
            {
                "   ": ExactScorer(),
            }
        )


def test_scorer_registry_is_not_changed_by_source_mapping_mutation() -> None:
    """
    Verify registry configuration is isolated from the caller's dictionary.

    The registry takes a copy during construction so later mutation of the
    source dictionary cannot alter an active benchmark configuration.
    """

    exact_scorer = ExactScorer()

    scorer_mapping: dict[str, BenchmarkScorer] = {
        "exact": exact_scorer,
    }

    scorer_registry = BenchmarkScorerRegistry(scorer_mapping)

    scorer_mapping.clear()

    assert scorer_registry.get_scorer("exact") is exact_scorer