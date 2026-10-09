"""
Deterministic exact-match benchmark scoring,

ExactScorer evaluates benchamark cases where the expected result can be compared directly with the observed result.

Current supported exact comparisons are:
    - router route_mode versus expected_route_mode;
    - model response_text versus expected_answer.

No fuzzy matching, semantic similarity, or model-assisted judgig occurs in this scorer.
Exact benchmarksshould remain deterministic and reproducable.
"""

from decimal import Decimal

from .data import BenchmarkCaseScore, BenchmarkCriterionScore, BenchmarkScoringRequest

_FULL_SCORE = Decimal("100")
_ZERO_SCORE = Decimal("0")
_RAW_PASS_SCORE = Decimal("1")
_RAW_FAIL_SCORE = Decimal("0")
_RAW_MAX_SCORE = Decimal("1")

_SCORER_TYPE = "exact"
_SCORER_VERSION = "1"

class ExactScorer:
    """
    Score deterministic benchmark cases using exact comparison.

    ExactSCroer is intentionally small and predictable.

    It evaluates one observed value against one expected value and converts
    the reslut into the Benchmark Service's normalized 0-100 quality scale.

    Current supported evaluation targets are:
        'router'
            Compare 'route_mode' with 'expected_route_mode'.
        'model'
            Compare 'response_text' with 'expected_answer'.

    A mismatch recieves a score of 0.

    An exact match recieves a score of 100.
    """

    def score(self, scoring_request: BenchmarkScoringRequest) -> BenchmarkCaseScore:
        """
        Score one determinitsic benchmark request.

        Args:
            scoring_request:
                Normalized benchmark definition and observed result.

        Returns:
            BenchmarkCaseScore:
                Immutable quality result containing the aggregate score and the exact-match criterion evidence.

        Raises:
            ValueError:
                Raised when scoring request does not use the 'exact' scoring method, 
                uses an unsupported evaluation target, or is missing required expected/observed values.
        """

        if scoring_request.scoring_method != "exact":
            raise ValueError("ExactScorer requires scoring_method='exact'")

        if scoring_request.evaluation_target == "router":
            return self._score_router_result(scoring_request)

        if scoring_request.evaluation_target == "model":
            return self._score_model_result(scoring_request)   

        raise ValueError("ExactScorer does not support evaluation_target='{}'".format(scoring_request.evaluation_target))

    def _score_router_result(self, scoring_request: BenchmarkScoringRequest) -> BenchmarkCaseScore:
        """
        Compare an observed router mode with the expected route mode and return a BenchmarkCaseScore.

        Args:
            scoring_request:
                Router benchmark scoring request.

        Returns:
            BenchmarkCaseScore:
                Deterministic router quality result.

        Raises:
            ValueError:
                Raised when either route-mode value is unavailable.
        """

        if scoring_request.expected_route_mode is None:
            raise ValueError("Exact router scoring requires expected_route_mode")

        if scoring_request.route_mode is None:
            raise ValueError("Exact router requires an observed route_mode")

        passed = scoring_request.route_mode == scoring_request.expected_route_mode

        return self._build_exact_score(
            benchmark_case_id=scoring_request.benchmark_case_id,
            criterion_name="route_mode_exact_match",
            passed=passed,
            expected_value=scoring_request.expected_route_mode,
            observed_value=scoring_request.route_mode,
        )

    def _score_model_result(self, scoring_request: BenchmarkScoringRequest) -> BenchmarkCaseScore:
        """
        Compare an observed model response with the expected answer and return a BenchmarkCaseScore.

        Args:
            scoring_request:
                Model benchmark scoring request.

        Returns:
            BenchmarkCaseScore:
                Deterministic model quality result.

        Raises:
            ValueError:
                Raised when either response or expected answer is unavailable.
        """

        if scoring_request.expected_answer is None:
            raise ValueError("Exact model scoring requires expected_answer")

        if scoring_request.response_text is None:
            raise ValueError("Exact model scoring requires an observed response_text")

        passed = scoring_request.response_text == scoring_request.expected_answer

        return self._build_exact_score(
            benchmark_case_id=scoring_request.benchmark_case_id,
            criterion_name="response_exact_match",
            passed=passed,
            expected_value=scoring_request.expected_answer,
            observed_value=scoring_request.response_text,
        )

    def _build_exact_score(
            self,
            *,
            benchmark_case_id: int,
            criterion_name: str,
            passed: bool,
            expected_value: str,
            observed_value: str,
    ) -> BenchmarkCaseScore:
        """
        Build normailized BenchmarkCaseScore and BenchmarkCriterionScore for an exact-match evaluation.

        Args:
            benchmark_case_id:
                Persistent identifier for the benchmark case.
            criterion_name:
                Stable criterion identifier describing the comparison being made.
            passed:
                True if the observed value matches the expected value, False otherwise.
            expected_value:
                The expected value for the benchmark case.
            observed_value:
                The observed value for the benchmark case.

        Returns:
            BenchmarkCaseScore:
                Complete deterministic quality result for the benchmark case.
        """

        raw_score = _RAW_PASS_SCORE if passed else _RAW_FAIL_SCORE

        normalized_score = _FULL_SCORE if passed else _ZERO_SCORE

        criterion_score = BenchmarkCriterionScore(
            criterion_name=criterion_name,
            raw_score=raw_score,
            normalized_score=normalized_score,
            max_score=_RAW_MAX_SCORE,
            passed=passed,
            scorer_type=_SCORER_TYPE,
            scorer_version=_SCORER_VERSION,
            details={
                "expected_value": expected_value,
                "observed_value": observed_value,
            },
        )

        diagnostic_text = "Observed value matches expected value" if passed else "Observed value does not match expected value"

        return BenchmarkCaseScore(
            benchmark_case_id=benchmark_case_id,
            normalized_quality_score=normalized_score,
            passed=passed,
            scorer_type=_SCORER_TYPE,
            scorer_version=_SCORER_VERSION,
            criterion_scores=(criterion_score,),
            diagnostic_text=diagnostic_text,
        )