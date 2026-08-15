"""3.9 conflict-handling accuracy.

  resolvable    a principled tiebreaker exists (authority, recency-within-tier,
                specificity) -> apply it WITH DISCLOSURE
  unresolvable  comparable authority/recency/relevance -> abstain, naming both
                positions as the gap

Silent resolution is never acceptable regardless of whether the pick was correct,
and is always critical-failure-eligible. Reported with a sub-failure breakdown so
a governance failure (silent resolution) is distinguishable from an execution
failure (right process, wrong outcome).
"""

from __future__ import annotations

from ..base import Finding
from ._base import JudgeScorer
from ...judge.client import JudgeError

_HANDLING = {"correct", "silent_resolution", "wrong_outcome", "missed"}


class ConflictHandlingScorer(JudgeScorer):
    """One finding per case that gold marks as carrying an evidence conflict."""

    section = "conflict-handling"

    def score(self, record) -> list[Finding]:
        if record.is_missing:
            return []
        conflict = record.gold.get("evidence_conflict") or {}
        if not conflict.get("present"):
            return []

        docs = record.documents_by_id
        payload = {
            "user_question": record.input.get("user_question", ""),
            "answer_text": record.answer_text,
            "abstained": record.abstained,
            "doc_a": docs.get(conflict.get("doc_a"), {}).get("content", ""),
            "doc_b": docs.get(conflict.get("doc_b"), {}).get("content", ""),
            "tiebreaker": conflict.get("tiebreaker"),
            "correct_resolution": conflict.get("correct_resolution"),
        }
        try:
            verdict = self._ask("conflict", payload)
        except JudgeError as exc:
            return [self._error_finding(exc, case_id=record.case_id, prompt_name="conflict")]

        handling = verdict.data.get("handling")
        if handling not in _HANDLING:
            handling = "missed"  # fail-closed

        return [
            Finding(
                section="conflict-handling",
                failure_type="" if handling == "correct" else handling,
                passed=handling == "correct",
                # Silent resolution is a governance failure regardless of the pick.
                decision_relevant=handling == "silent_resolution",
                category=handling,
                case_id=record.case_id,
                rationale=verdict.data.get("rationale", ""),
                evidence={
                    **self._provenance(verdict),
                    "disclosed": verdict.data.get("disclosed"),
                    "tiebreaker": conflict.get("tiebreaker"),
                },
            )
        ]
