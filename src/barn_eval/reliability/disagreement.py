"""Judge vs reference disagreement reporting (Part Two: "on LLM judges").

An LLM judge may be one component of the evaluator but never the only one. Where a
metric has both a judge verdict and an independent reference - a deterministic
check, a hand label, or manual review - the disagreement rate is reported per
metric rather than silently resolved in favour of either side. A high
disagreement rate is a reason to distrust the judge on that metric, independent of
the invariance (flip-rate) result.

Primary reference here: evaluation_cases/groundability_audit.jsonl - hand-labelled
groundedness items (grounded / unsupported / citation_failure{overreach,
wrong_source}) whose payload is exactly what the groundedness scorer sends the
judge, so the judge is exercised on the same task it does in a real run.

This is a diagnostic, not a gate: it characterises the judge for the evaluation
card and points reviewers at the specific items to audit. The release-blocking
signal is the invariance flip rate (gate 5).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ..judge.client import JudgeError

# The groundedness scorer's fail-closed default category on an unparseable verdict.
_FALLBACK_CATEGORY = "unsupported"
_CATEGORIES = {"grounded", "unsupported", "citation_failure"}


@dataclass
class AuditItem:
    audit_id: str
    source: str
    judge_category: str
    judge_subtype: object
    gold_category: str
    gold_subtype: object
    agree: bool
    judge_error: bool = False


@dataclass
class DisagreementReport:
    """Per-metric agreement of the judge against a reference set."""

    metric: str
    n: int                 # items compared (judge_error items excluded)
    agreements: int
    judge_errors: int
    items: list[AuditItem] = field(default_factory=list)

    @property
    def disagreements(self) -> int:
        return self.n - self.agreements

    @property
    def disagreement_rate(self) -> float:
        return (self.disagreements / self.n) if self.n else 0.0

    @property
    def agreement_rate(self) -> float:
        return (self.agreements / self.n) if self.n else 0.0

    def to_dict(self) -> dict:
        return {
            "metric": self.metric,
            "n": self.n,
            "agreements": self.agreements,
            "disagreements": self.disagreements,
            "disagreement_rate": self.disagreement_rate,
            "judge_errors": self.judge_errors,
            "mismatches": [
                {
                    "audit_id": it.audit_id,
                    "source": it.source,
                    "gold": it.gold_category,
                    "gold_subtype": it.gold_subtype,
                    "judge": it.judge_category,
                    "judge_subtype": it.judge_subtype,
                }
                for it in self.items
                if not it.agree and not it.judge_error
            ],
        }


def load_groundability_audit(path: str | Path) -> list[dict]:
    """Read the hand-labelled groundedness reference (one JSON object per line)."""
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def _agrees(judge_cat: str, judge_sub, gold_cat: str, gold_sub) -> bool:
    """Category must match; for citation_failure the wrong_source/overreach subtype
    must match too, since overreach on a decision-relevant claim escalates to a
    critical failure while wrong_source does not - conflating them would hide a
    material disagreement."""
    if judge_cat != gold_cat:
        return False
    if gold_cat == "citation_failure":
        return (judge_sub or None) == (gold_sub or None)
    return True


def audit_groundedness(judge, audit: list[dict], metric: str = "grounded") -> DisagreementReport:
    """Run the groundedness judge over the reference items and report disagreement.

    judge   a callable(prompt_name, payload) -> JudgeVerdict (the same seam the
            scorers use); tests inject a scripted fake, so no network is required.
    """
    items: list[AuditItem] = []
    agreements = judge_errors = 0
    for row in audit:
        payload = {
            "user_question": row.get("user_question", ""),
            "claim_text": row.get("claim_text", ""),
            "cited_documents": row.get("cited_documents", []),
        }
        try:
            verdict = judge("groundedness", payload)
        except JudgeError:
            judge_errors += 1
            items.append(AuditItem(
                audit_id=row.get("audit_id", ""), source=row.get("source", ""),
                judge_category="judge_error", judge_subtype=None,
                gold_category=row.get("gold_category", ""), gold_subtype=row.get("gold_subtype"),
                agree=False, judge_error=True,
            ))
            continue
        cat = verdict.data.get("category")
        if cat not in _CATEGORIES:
            cat = _FALLBACK_CATEGORY  # mirror the scorer's fail-closed default
        sub = verdict.data.get("citation_failure_subtype")
        agree = _agrees(cat, sub, row.get("gold_category", ""), row.get("gold_subtype"))
        agreements += int(agree)
        items.append(AuditItem(
            audit_id=row.get("audit_id", ""), source=row.get("source", ""),
            judge_category=cat, judge_subtype=sub,
            gold_category=row.get("gold_category", ""), gold_subtype=row.get("gold_subtype"),
            agree=agree,
        ))
    n = len(audit) - judge_errors
    return DisagreementReport(metric=metric, n=n, agreements=agreements, judge_errors=judge_errors, items=items)
