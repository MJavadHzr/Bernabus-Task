"""Scorer protocol.

Every scorer takes one EvaluationRecord and returns findings. Case-level
scoring stays separate from aggregation: a scorer never computes a rate, and
aggregation never inspects a claim.

Each Finding carries: metric section, failure type, severity (derived), whether
the claim was decision-relevant, and the evidence for the verdict. Severity is
derived here from failure type and decision-relevance (3.13); the case's
expected_failure_severity is used only to flag divergence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

# Severity ordering, used by aggregation/gates. "none" is a clean observation.
SEVERITY_ORDER = ("none", "minor", "moderate", "major", "critical")


@dataclass
class Finding:
    """One scored observation for one EvaluationRecord.

    A Finding is an observation, never a rate. Aggregation reads a stream of
    Findings and computes numerator/denominator per metric; a scorer emits one
    Finding per scored unit (claim, citation, case, or injected instruction).

    Fields
      section          Part One / Part Two clause, e.g. "3.5", "4.1"
      failure_type     stable machine key, e.g. "fabricated_citation"; "" if a pass
      passed           True  -> the unit satisfied the metric (or is a clean measure)
                       False -> the unit failed; failure_type names how
      severity         derived from failure_type + decision_relevant (3.13)
      decision_relevant  whether the underlying claim is decision-relevant (3.12)
      category         taxonomy bucket where a metric partitions one denominator
                       (e.g. grounded / unsupported / citation_failure)
      unit_id          claim_id / citation / instruction_id / None (case-level)
      counts_denominator  whether this unit belongs in the metric's denominator
      value            optional numeric payload (latency_ms, cost_usd, ...)
      rationale        human-readable justification
      evidence         structured supporting detail (source ids, spans, hashes)
    """

    section: str
    failure_type: str = ""
    passed: bool = True
    severity: str = "none"
    decision_relevant: bool = False
    category: Optional[str] = None
    unit_id: Optional[str] = None
    case_id: Optional[str] = None
    counts_denominator: bool = True
    value: Optional[float] = None
    rationale: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)

    @property
    def is_failure(self) -> bool:
        return not self.passed


class Scorer:
    """Base protocol. `section` names the Part One clause the scorer implements.

    `deterministic` marks the §5 exemption: everything under scorers/deterministic
    sets it True, everything under scorers/judge leaves it False. The value is a
    machine-checkable mirror of the directory the scorer lives in.
    """

    section: str = ""
    deterministic: bool = False

    def score(self, record) -> list[Finding]:
        """Return a list of Findings for one EvaluationRecord."""
        raise NotImplementedError
