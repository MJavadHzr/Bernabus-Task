"""Decision-relevance determination against gold.decision_relevant_criteria.

A claim is decision-relevant if its falsification or reversal would change the
clinical action a reasonable clinician takes.

This is the highest-leverage judge call in the framework: after the v1.1 collapse
of 3.12 item 5, decision_relevant_criteria is GATE-FIRING - a citation overreach
on a decision-relevant claim is a critical failure. This scorer therefore emits a
determination per claim (passed=True observation, decision_relevant flag set) that
downstream gating joins against the groundedness/prohibited findings by claim_id.
It does not itself fail a claim; it labels one.
"""

from __future__ import annotations

from ..base import Finding
from ._base import JudgeScorer
from ...judge.client import JudgeError


class DecisionRelevanceScorer(JudgeScorer):
    """One labelling finding per claim. No criteria -> nothing to label."""

    section = "3.12"

    def score(self, record) -> list[Finding]:
        if record.is_missing or record.abstained:
            return []
        criteria = record.gold.get("decision_relevant_criteria") or []
        if not criteria:
            return []  # gate-firing field is unauthored; do not invent relevance

        findings: list[Finding] = []
        for claim in record.claims:
            claim_id = claim.get("claim_id")
            payload = {
                "user_question": record.input.get("user_question", ""),
                "claim_text": claim.get("text", ""),
                "decision_relevant_criteria": criteria,
            }
            try:
                verdict = self._ask("decision_relevance", payload)
            except JudgeError as exc:
                findings.append(
                    self._error_finding(exc, case_id=record.case_id, unit_id=claim_id, prompt_name="decision_relevance")
                )
                continue

            relevant = bool(verdict.data.get("decision_relevant"))
            findings.append(
                Finding(
                    section="3.12",
                    failure_type="",
                    passed=True,  # a determination, never a failure on its own
                    decision_relevant=relevant,
                    category="decision_relevant" if relevant else "background",
                    unit_id=claim_id,
                    case_id=record.case_id,
                    rationale=verdict.data.get("rationale", ""),
                    evidence={
                        **self._provenance(verdict),
                        "matched_criterion": verdict.data.get("matched_criterion"),
                    },
                )
            )
        return findings
