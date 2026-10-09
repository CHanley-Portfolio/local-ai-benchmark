"""
Registry for Benchmark Service quality scorers.

The registry maps benchmark scoring-method identifiers to concrete scorer
implementations.

Application orchestration should use this registry rather than containing
scoring-method-specific conditional logic.
"""

from collections.abc import Mapping

from .scorer import BenchmarkScorer


class BenchmarkScorerRegistry:
    """
    Resolve benchmark scoring methods to scorer implementations.

    The registry itself does not know how any scoring algorithm works.

    Its responsibility is limited to mapping a stable scoring-method name,
    such as ``exact``, to an object implementing BenchmarkScorer.

    Keeping this lookup separate from orchestration prevents future code from
    accumulating repeated ``if/elif`` branches for every scoring mechanism.
    """

    def __init__(
        self,
        scorers: Mapping[str, BenchmarkScorer],
    ) -> None:
        """
        Create a scorer registry.

        Args:
            scorers:
                Mapping from scoring-method identifiers to compatible scorer
                implementations.

                Example:

                    {
                        "exact": ExactScorer(),
                    }

        Raises:
            ValueError:
                Raised if a blank scoring-method identifier is supplied.
        """

        for scoring_method in scorers:
            if not scoring_method.strip():
                raise ValueError(
                    "Benchmark scorer registry cannot contain a blank "
                    "scoring-method identifier."
                )

        # Copy the supplied mapping so external mutation of the original
        # dictionary cannot silently change registry behavior later.
        self._scorers = dict(scorers)

    def get_scorer(
        self,
        scoring_method: str,
    ) -> BenchmarkScorer:
        """
        Return the scorer registered for a benchmark scoring method.

        Args:
            scoring_method:
                Stable scoring-method identifier from the benchmark case.

        Returns:
            BenchmarkScorer:
                Scorer responsible for evaluating that scoring method.

        Raises:
            ValueError:
                Raised when the requested scoring method has no registered
                implementation.
        """

        benchmark_scorer = self._scorers.get(scoring_method)

        if benchmark_scorer is None:
            supported_scoring_methods = ", ".join(
                sorted(self._scorers)
            )

            if not supported_scoring_methods:
                supported_scoring_methods = "none"

            raise ValueError(
                "No benchmark scorer is registered for "
                f"scoring_method='{scoring_method}'. "
                "Supported scoring methods: "
                f"{supported_scoring_methods}."
            )

        return benchmark_scorer