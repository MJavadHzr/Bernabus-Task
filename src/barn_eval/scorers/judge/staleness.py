"""3.10 staleness-handling accuracy.

Newer wins on the relevant clock, with disclosure. Staleness is subordinate to
authority: a newer low-tier document never overrides an older high-tier one.

Sub-failure types, separable only because gold declares wrong_clock_conclusion:
  wrong_clock            conclusion matches wrong_clock_conclusion
  tier_subordination     right clock, lower tier wrongly preferred
  no_disclosure          right clock and tier, update not disclosed

Residual limitation: reasoning is unobserved, so "used the right clock" is
inferred from the conclusion; a system reaching the right answer by the wrong
route scores as a pass.
"""

from __future__ import annotations

from ..base import Finding
from ._base import JudgeScorer
from ...judge.client import JudgeError

_HANDLING = {"correct", "wrong_clock", "tier_subordination", "no_disclosure"}


class StalenessHandlingScorer(JudgeScorer):
    """One finding per case that gold marks as carrying stale-vs-current evidence."""

    section = "staleness-handling"

    def score(self, record) -> list[Finding]:
        if record.is_missing:
            return []
        stale = record.gold.get("evidence_staleness") or {}
        if not stale.get("present"):
            return []

        docs = record.documents_by_id

        def _doc(source_id):
            d = docs.get(source_id) or {}
            return {"source_id": source_id, "content": d.get("content", ""), "authority": d.get("source_authority")}

        payload = {
            "user_question": record.input.get("user_question", ""),
            "answer_text": record.answer_text,
            "stale_document": _doc(stale.get("stale_doc_id")),
            "current_document": _doc(stale.get("current_doc_id")),
            "relevant_clock": stale.get("relevant_clock"),
            "wrong_clock_conclusion": stale.get("wrong_clock_conclusion"),
        }
        try:
            verdict = self._ask("staleness", payload)
        except JudgeError as exc:
            return [self._error_finding(exc, case_id=record.case_id, prompt_name="staleness")]

        handling = verdict.data.get("handling")
        if handling not in _HANDLING:
            handling = "wrong_clock"  # fail-closed

        return [
            Finding(
                section="staleness-handling",
                failure_type="" if handling == "correct" else handling,
                passed=handling == "correct",
                category=handling,
                case_id=record.case_id,
                rationale=verdict.data.get("rationale", ""),
                evidence={**self._provenance(verdict), "relevant_clock": stale.get("relevant_clock")},
            )
        ]
