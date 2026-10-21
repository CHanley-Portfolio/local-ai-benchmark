"""
Machine-readable historical benchmark-run comparison
"""

from dataclasses import dataclass

from .benchmark_case_comparison import BenchmarkCaseComparison


@dataclass(frozen=True)
class BenchmarkRunComparison:
    """
    Compare two historical executions of the same benchmark suite.

    The comparison preserves configuration identifiers so future reporting can explain whether
      a difference occured across models, hardware, runtime, context configuration, source code, 
      or some combination of those factors. 
    """

    baseline_run_id: int
    comparison_run_id: int

    benchmark_suite_id: int

    baseline_model_profile_id: int
    comparison_model_profile_id: int

    baseline_hardware_profile_id: int
    comparison_hardware_profile_id: int

    baseline_runtime_profile_id: int
    comparison_runtime_profile_id: int

    baseline_context_profile_id: int | None
    comparison_context_profile_id: int | None

    baseline_source_git_commit: str | None
    comparison_source_git_commit: str | None

    case_comparisons: tuple[BenchmarkCaseComparison, ...]

    total_case_count: int

    pass_regression_count: int
    execution_regression_count: int
    quality_regression_count: int
    quality_improvement_count: int

    has_regressions: bool