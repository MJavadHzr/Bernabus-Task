"""Scorer protocol.

Every scorer takes one EvaluationRecord and returns findings. Case-level
scoring stays separate from aggregation: a scorer never computes a rate, and
aggregation never inspects a claim.

Each Finding carries: metric section, failure type, severity (derived), whether
the claim was decision-relevant, and the evidence for the verdict. Severity is
derived here from failure type and decision-relevance (3.13); the case's
expected_failure_severity is used only to flag divergence.
"""


class Scorer:
    """Base protocol. `section` names the Part One clause the scorer implements."""

    section: str = ""
    deterministic: bool = False

    def score(self, record):
        """Return a list of Findings for one EvaluationRecord."""
        raise NotImplementedError


class Finding:
    """One scored observation: section, failure_type, severity, decision_relevant,
    claim_id, rationale, evidence."""
