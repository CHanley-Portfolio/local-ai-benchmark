"""
Criterion-level quality score produced by benchmark scoring.

A single benchmark case can contain multiple scoring criteria.

For example, a coding benchmark might seperately evaluate:
    - correct FastAPI usage;
    - request/response model seperation;
    - input validation;
    - route correctness;
    - response fields.

Keeping each criterion as its own immutable result preserves the evidence
behind the final normalized benchmark score.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class BenchmarkCriterionScore:
    """
    Represent the score assigneed to one benchmark evaluation criterion.

    The Benchmark Service methodology currently defines rubric criteria on a 0-4 scale, 
    but this contract deliberately stores both 'raw_score' and 'max_score' so future deterministic 
    or executable scorers can use a different natural scale without changing the persistence model.
    
    Attributes:
        criterion_name:
            Human-readable criterion being evaluated.

            For rubric benchmarks this will normally be one entry from 
            the benchmark case's 'expected_criteria' collection.

        raw_score:
            Score assigned using the scorer's native scale.

            Example:
                A rubric scorer may assign '3' out of '4'.
            
        max_score:
            Maximum possibleraw score for this criterion.

        normalized_score:
            Criterion score converted to the common 0-100 quality scale.

            Example:
                3/4 becomes 75.
        
        passed:
            Whether this individual criterion satisfied its passing rule.

        scorer_type:
            Stable identifiers describing the scoring mechanism,

            Examples might eventually include:
                'Exact'
                'Rubric'
                'executable_test'

        scorer_version:
            Optional scorer implementation/version identifier.

            Recording theis allows historical benchmark results to remain
            interpretable if the scoring implementation changes later.

        details:
            optional structured diagnostic information produced by the scorer.

            This should contain scoring evidence or metadata rather than replacing the human-readable criterion itself.
    """

    criterion_name: str

    raw_score: Decimal
    max_score: Decimal
    normalized_score: Decimal

    passed: bool

    scorer_type:str
    scorer_version: str | None = None

    details: dict[str, Any] | None = None

