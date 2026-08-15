"""Evaluate-the-evaluator (Phase 6). Block condition 3.14.5.

Two independent checks on the evaluator itself:

  invariance    a meaning-preserving perturbation must not change a verdict; the
                verdict-flip rate feeds gate 5 and takes precedence over any system
                score (invariance.py + perturbations.py)
  disagreement  where a metric has a reference label, the judge is compared against
                it and disagreement is reported, never silently resolved
                (disagreement.py)

The runner leaves gate 5 NOT_EVALUATED until this runs; the CLI `reliability`
command produces a ReliabilityReport whose verdict_flip_rate is then handed to a
`run` via --reliability.
"""

from .disagreement import (
    AuditItem,
    DisagreementReport,
    audit_groundedness,
    load_groundability_audit,
)
from .invariance import (
    Flip,
    PerturbationResult,
    ReliabilityReport,
    UnitVerdict,
    run_invariance,
)
from .perturbations import PERTURBATIONS, default_perturbations

__all__ = [
    "run_invariance",
    "ReliabilityReport",
    "PerturbationResult",
    "Flip",
    "UnitVerdict",
    "PERTURBATIONS",
    "default_perturbations",
    "audit_groundedness",
    "load_groundability_audit",
    "DisagreementReport",
    "AuditItem",
]
