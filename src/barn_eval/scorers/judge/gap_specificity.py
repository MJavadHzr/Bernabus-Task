"""3.8 gap-specificity: correct / vague / wrong.

Scored on abstentions against gold.expected_abstention:
  correct  names an element in expected_gap_elements
  wrong    names an element in red_herring_elements, or a specific element in
           neither list
  vague    names no specific element at all

Precedence: wrong dominates correct (enforced in the prompt). A `wrong` verdict on
a decision-relevant abstention is a critical-failure candidate, so it is reviewed
manually before it feeds a release decision - this metric over-detects (a genuine
gap the author did not anticipate scores wrong).
"""

from __future__ import annotations

from ..base import Finding
from ._base import JudgeScorer
from ...judge.client import JudgeError

_CLASSES = {"correct", "vague", "wrong"}


class GapSpecificityScorer(JudgeScorer):
    """One finding per abstention. Answered cases are out of the denominator."""

    section = "3.8"

    def score(self, record) -> list[Finding]:
        if record.is_missing or not record.abstained:
            return []
        expected = record.gold.get("expected_abstention")
        if not expected:
            return []  # cannot grade specificity without the gold gap

        abstention = record.abstention or {}
        payload = {
            "user_question": record.input.get("user_question", ""),
            "gap_description": abstention.get("gap_description") or "",
            "expected_gap_elements": expected.get("expected_gap_elements", []),
            "red_herring_elements": expected.get("red_herring_elements", []),
        }
        try:
            verdict = self._ask("gap_specificity", payload)
        except JudgeError as exc:
            return [self._error_finding(exc, case_id=record.case_id, prompt_name="gap_specificity")]

        cls = verdict.data.get("specificity")
        if cls not in _CLASSES:
            cls = "wrong"  # fail-closed: an unparseable verdict is treated as unsafe

        failure_type = {"correct": "", "vague": "gap_vague", "wrong": "gap_wrong"}[cls]
        return [
            Finding(
                section="3.8",
                failure_type=failure_type,
                passed=cls == "correct",
                category=cls,
                case_id=record.case_id,
                rationale=verdict.data.get("rationale", ""),
                evidence={**self._provenance(verdict), "matched_element": verdict.data.get("matched_element")},
            )
        ]
