"""Shared base for judge-backed scorers.

Every scorer here holds an INJECTED judge callable (Judge, or a scripted fake in
tests) with signature `judge(prompt_name, payload) -> JudgeVerdict`. Nothing here
constructs a judge or reads config; the runner wires that in Part Eight, and
tests inject fakes, so no judge-scorer test touches the network.

Fail-closed: a judge that errors on a unit does NOT yield a clean pass. It yields
a visible `judge_error` finding for that unit (passed=False) and scoring
continues on the remaining units.
"""

from __future__ import annotations

from typing import Optional

from ...judge.client import JudgeError, JudgeVerdict
from ..base import Finding, Scorer


class JudgeScorer(Scorer):
    """Base for §5-burdened semantic scorers. `deterministic` stays False."""

    deterministic = False

    def __init__(self, judge):
        # judge: callable(prompt_name: str, payload: dict) -> JudgeVerdict
        self.judge = judge

    def _ask(self, prompt_name: str, payload: dict) -> JudgeVerdict:
        return self.judge(prompt_name, payload)

    def _error_finding(
        self,
        exc: JudgeError,
        *,
        case_id: str,
        unit_id: Optional[str] = None,
        prompt_name: str = "",
    ) -> Finding:
        return Finding(
            section=self.section,
            failure_type="judge_error",
            passed=False,
            counts_denominator=False,  # not a system failure; an evaluator outage
            unit_id=unit_id,
            case_id=case_id,
            rationale=f"judge call failed (fail-closed, not a clean pass): {exc}",
            evidence={"prompt": prompt_name, "error": str(exc)},
        )

    @staticmethod
    def _provenance(verdict: JudgeVerdict) -> dict:
        return {
            "judge_model": verdict.model,
            "prompt_name": verdict.prompt_name,
            "prompt_version": verdict.prompt_version,
        }
