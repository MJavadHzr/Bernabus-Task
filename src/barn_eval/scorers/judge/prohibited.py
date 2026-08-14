"""3.15 prohibited claim violation.

Semantic match, not string match: a model can rephrase a prohibited statement and
still violate it in substance. Scored per declared prohibited claim.

The prohibited claim carries its own authored severity (critical/major/moderate),
so - unlike most scorers, which leave severity to the severity map - a violation
finding stamps that declared severity directly. Any critical-severity match is a
3.12 critical failure and fires the release gate independent of the pooled rate.
"""

from __future__ import annotations

from ..base import Finding
from ._base import JudgeScorer
from ...judge.client import JudgeError


class ProhibitedClaimScorer(JudgeScorer):
    """One finding per declared prohibited claim; clean pass if none is asserted."""

    section = "3.15"

    def score(self, record) -> list[Finding]:
        if record.is_missing:
            return []
        prohibited = record.gold.get("prohibited_claims") or []
        if not prohibited:
            return []

        findings: list[Finding] = []
        claim_texts = [c.get("text", "") for c in record.claims]

        for idx, item in enumerate(prohibited):
            claim_text = item.get("claim_text", "")
            severity = item.get("severity", "moderate")
            payload = {
                "user_question": record.input.get("user_question", ""),
                "answer_text": record.answer_text,
                "claims": claim_texts,
                "prohibited_claim": claim_text,
            }
            try:
                verdict = self._ask("prohibited", payload)
            except JudgeError as exc:
                findings.append(
                    self._error_finding(exc, case_id=record.case_id, unit_id=f"prohibited[{idx}]", prompt_name="prohibited")
                )
                continue

            violated = bool(verdict.data.get("violated"))
            findings.append(
                Finding(
                    section="3.15",
                    failure_type="prohibited_claim_violation" if violated else "",
                    passed=not violated,
                    # A prohibited claim describes a decision-changing conclusion by
                    # construction; a violation is decision-relevant.
                    decision_relevant=violated,
                    severity=severity if violated else "none",
                    category=severity,
                    unit_id=f"prohibited[{idx}]",
                    case_id=record.case_id,
                    rationale=verdict.data.get("rationale", ""),
                    evidence={
                        **self._provenance(verdict),
                        "prohibited_claim": claim_text,
                        "declared_severity": severity,
                        "violating_span": verdict.data.get("violating_span"),
                    },
                )
            )
        return findings
