"""
Tests for deterministic exact benchmark scoring.

Exact scoring must remain reproducible and must not depend on external
services, probabilistic models, or fuzzy comparison behavior.
"""

from decimal import Decimal

import pytest

from local_ai_benchmark.scoring import (
    BenchmarkScorer,
    BenchmarkScoringRequest,
    ExactScorer,
)


def test_exact_scorer_passes_matching_router_mode() -> None:
    """
    Verify an exact router-mode match receives full quality credit.
    """

    scorer = ExactScorer()

    scoring_result = scorer.score(
        BenchmarkScoringRequest(
            benchmark_case_id=101,
            evaluation_target="router",
            scoring_method="exact",
            route_mode="reasoning",
            expected_route_mode="reasoning",
        )
    )

    assert scoring_result.benchmark_case_id == 101
    assert scoring_result.normalized_quality_score == Decimal("100")
    assert scoring_result.passed is True

    assert scoring_result.scorer_type == "exact"
    assert scoring_result.scorer_version == "1"

    assert len(scoring_result.criterion_scores) == 1

    criterion_score = scoring_result.criterion_scores[0]

    assert criterion_score.criterion_name == "route_mode_exact_match"
    assert criterion_score.raw_score == Decimal("1")
    assert criterion_score.max_score == Decimal("1")
    assert criterion_score.normalized_score == Decimal("100")
    assert criterion_score.passed is True

    assert criterion_score.details == {
        "expected_value": "reasoning",
        "observed_value": "reasoning",
    }


def test_exact_scorer_fails_mismatched_router_mode() -> None:
    """
    Verify an incorrect router mode receives zero quality credit.
    """

    scorer = ExactScorer()

    scoring_result = scorer.score(
        BenchmarkScoringRequest(
            benchmark_case_id=102,
            evaluation_target="router",
            scoring_method="exact",
            route_mode="fast",
            expected_route_mode="reasoning",
        )
    )

    assert scoring_result.normalized_quality_score == Decimal("0")
    assert scoring_result.passed is False

    criterion_score = scoring_result.criterion_scores[0]

    assert criterion_score.raw_score == Decimal("0")
    assert criterion_score.normalized_score == Decimal("0")
    assert criterion_score.passed is False

    assert criterion_score.details == {
        "expected_value": "reasoning",
        "observed_value": "fast",
    }


def test_exact_scorer_passes_matching_model_response() -> None:
    """
    Verify model text can also use deterministic exact scoring.
    """

    scorer = ExactScorer()

    scoring_result = scorer.score(
        BenchmarkScoringRequest(
            benchmark_case_id=201,
            evaluation_target="model",
            scoring_method="exact",
            response_text="503",
            expected_answer="503",
        )
    )

    assert scoring_result.normalized_quality_score == Decimal("100")
    assert scoring_result.passed is True

    criterion_score = scoring_result.criterion_scores[0]

    assert criterion_score.criterion_name == "response_exact_match"
    assert criterion_score.details == {
        "expected_value": "503",
        "observed_value": "503",
    }


def test_exact_scorer_does_not_silently_normalize_model_text() -> None:
    """
    Verify exact scoring does not secretly become fuzzy matching.

    A trailing space changes the observed string and therefore must fail an
    exact comparison.
    """

    scorer = ExactScorer()

    scoring_result = scorer.score(
        BenchmarkScoringRequest(
            benchmark_case_id=202,
            evaluation_target="model",
            scoring_method="exact",
            response_text="503 ",
            expected_answer="503",
        )
    )

    assert scoring_result.normalized_quality_score == Decimal("0")
    assert scoring_result.passed is False


def test_exact_scorer_rejects_wrong_scoring_method() -> None:
    """
    Verify ExactScorer cannot accidentally score a rubric benchmark.
    """

    scorer = ExactScorer()

    with pytest.raises(
        ValueError,
        match="requires scoring_method='exact'",
    ):
        scorer.score(
            BenchmarkScoringRequest(
                benchmark_case_id=301,
                evaluation_target="model",
                scoring_method="rubric",
                response_text="answer",
            )
        )


def test_exact_scorer_requires_expected_router_mode() -> None:
    """
    Verify router scoring cannot proceed without its expected value.
    """

    scorer = ExactScorer()

    with pytest.raises(
        ValueError,
        match="requires expected_route_mode",
    ):
        scorer.score(
            BenchmarkScoringRequest(
                benchmark_case_id=302,
                evaluation_target="router",
                scoring_method="exact",
                route_mode="fast",
            )
        )


def test_exact_scorer_requires_observed_router_mode() -> None:
    """
    Verify router scoring cannot proceed without observed evidence.
    """

    scorer = ExactScorer()

    with pytest.raises(
        ValueError,
        match="requires an observed route_mode",
    ):
        scorer.score(
            BenchmarkScoringRequest(
                benchmark_case_id=303,
                evaluation_target="router",
                scoring_method="exact",
                expected_route_mode="fast",
            )
        )


def test_exact_scorer_rejects_unsupported_evaluation_target() -> None:
    """
    Verify unsupported evaluation targets fail explicitly.
    """

    scorer = ExactScorer()

    with pytest.raises(
        ValueError,
        match="does not support evaluation_target",
    ):
        scorer.score(
            BenchmarkScoringRequest(
                benchmark_case_id=304,
                evaluation_target="unknown",
                scoring_method="exact",
            )
        )


def test_exact_scorer_satisfies_benchmark_scorer_protocol() -> None:
    """
    Verify ExactScorer satisfies the common scorer interface.
    """

    scorer = ExactScorer()

    assert isinstance(scorer, BenchmarkScorer)