"""3.1 correct answer rate.

Compares the final conclusion against gold.expected_conclusion. Scored only on
answered cases with a declared expected_conclusion. Judged on the CONCLUSION, not
the reasoning - reasoning quality is groundedness's job.

Limitation carried into the report: this does not catch a right conclusion
reached through ungrounded reasoning, so it is never reported without
groundedness beside it.
"""

from __future__ import annotations

from ..base import Finding
from ._base import JudgeScorer
from ...judge.client import JudgeError


class CorrectnessScorer(JudgeScorer):
    """One case-level finding: does the conclusion match gold?"""

    section = "3.1"

    def score(self, record) -> list[Finding]:
        if record.is_missing or record.abstained:
            return []
        expected = record.gold.get("expected_conclusion")
        if not expected:
            return []  # no gold conclusion to grade against

        payload = {
            "user_question": record.input.get("user_question", ""),
            "answer_text": record.answer_text,
            "expected_conclusion": expected,
        }
        try:
            verdict = self._ask("correctness", payload)
        except JudgeError as exc:
            return [self._error_finding(exc, case_id=record.case_id, prompt_name="correctness")]

        correct = bool(verdict.data.get("correct"))
        return [
            Finding(
                section="3.1",
                failure_type="" if correct else "incorrect_answer",
                passed=correct,
                case_id=record.case_id,
                rationale=verdict.data.get("rationale", ""),
                evidence={**self._provenance(verdict), "expected_conclusion": expected},
            )
        ]
