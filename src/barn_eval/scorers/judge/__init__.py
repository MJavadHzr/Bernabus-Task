"""Semantic judgments. Every scorer here is subject to the §5 reliability
requirement, and instability in any of them is block condition 3.14.5 - which
takes precedence over any score the system under test receives.

Each must be compared against a deterministic check, a reference label or manual
review, with disagreements reported (Part Two, "on LLM judges").

Unlike the deterministic scorers, these are NOT instantiable with no arguments:
each holds an injected judge callable. `JUDGE_SCORERS` is the class list (the §5
burden set, mirroring the directory listing); `build_judge_scorers(judge)`
instantiates them all with one shared judge.
"""

from .conflict import ConflictHandlingScorer
from .correctness import CorrectnessScorer
from .decision_relevance import DecisionRelevanceScorer
from .gap_specificity import GapSpecificityScorer
from .groundedness import GroundednessScorer
from .injection import InjectionResistanceScorer
from .prohibited import ProhibitedClaimScorer
from .staleness import StalenessHandlingScorer

# The class list IS the §5 reliability-burden set (parallel to DETERMINISTIC_SCORERS).
JUDGE_SCORERS = [
    GroundednessScorer,
    CorrectnessScorer,
    DecisionRelevanceScorer,
    ProhibitedClaimScorer,
    GapSpecificityScorer,
    ConflictHandlingScorer,
    StalenessHandlingScorer,
    InjectionResistanceScorer,
]


def build_judge_scorers(judge):
    """Instantiate every judge scorer with one shared, injected judge callable."""
    return [cls(judge) for cls in JUDGE_SCORERS]


__all__ = [
    "ConflictHandlingScorer",
    "CorrectnessScorer",
    "DecisionRelevanceScorer",
    "GapSpecificityScorer",
    "GroundednessScorer",
    "InjectionResistanceScorer",
    "ProhibitedClaimScorer",
    "StalenessHandlingScorer",
    "JUDGE_SCORERS",
    "build_judge_scorers",
]
