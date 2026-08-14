"""3.13 harm-weighting. Gating, not multiplying.

Derives observed severity from failure type and decision-relevance. The case's
gold.expected_failure_severity is NOT the score - it is the severity the author
expected the case to carry if failed, used to validate case design and flag
divergence. Persistent disagreement between derived and expected usually means
the case is not testing what its author believed.

Two facts make this module more than a dict lookup:

1. Decision-relevance is a SEPARATE per-claim determination (scorers/judge/
   decision_relevance.py), so severity of a claim-level failure must be resolved
   by JOINING the failure to that claim's decision-relevance label. A failure that
   self-declares decision_relevant (false_certainty, silent_resolution, a critical
   prohibited claim) short-circuits the join fail-closed.

2. Scorers emit specific mechanism names (`silent_resolution`, `incorrect_answer`,
   `gap_wrong`); the §3.13 table is authored at a coarser grain
   (`silent_conflict_resolution`, `incorrect_conclusion`, `gap_specificity_wrong`).
   `_FAILURE_ALIAS` is the explicit, reviewable bridge between the two.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

# Scorer failure_type  ->  severity_map.yaml canonical key. Explicit on purpose:
# a silent mismatch here would drop a failure into the wrong severity tier.
_FAILURE_ALIAS = {
    # the eight §3.12 critical triggers (decision_relevant map keys)
    "fabricated_citation": "fabricated_citation",
    "false_certainty": "false_certainty",
    "context_contamination": "context_contamination",
    "silent_resolution": "silent_conflict_resolution",
    "citation_overreach": "citation_overreach",
    "promotion_by_assertion": "authority_violation",
    "unauthorised_promotion": "authority_violation",
    "broken_provenance": "authority_violation",
    "incorrect_answer": "incorrect_conclusion",
    "gap_wrong": "gap_specificity_wrong",
    # lesser / non-decision-relevant tiers
    "citation_failure": "citation_failure",
    "unsupported_claim": "unsupported_claim",
    "unnecessary_abstention": "unnecessary_abstention_high_stakes",  # fail-closed to high
    "gap_vague": "gap_specificity_vague",
}

# Prohibited claims carry their own authored severity; not remapped here.
_PROHIBITED = "prohibited_claim_violation"
# An evaluator outage is not a system-severity event; it is surfaced separately.
_JUDGE_ERROR = "judge_error"


@dataclass(frozen=True)
class SeverityMap:
    """The §3.13 table, loaded from configs/severity_map.yaml."""

    decision_relevant: dict[str, str]
    not_decision_relevant: dict[str, str]
    prohibited_source: str = "case"

    @property
    def critical_triggers(self) -> frozenset[str]:
        """The eight §3.12 trigger keys == the decision_relevant map's keys."""
        return frozenset(self.decision_relevant)

    def derive(self, failure_type: str, decision_relevant: bool, authored_severity: str = "") -> str:
        """Severity for one failure, given whether its claim is decision-relevant.

        Order: prohibited (authored) -> alias -> decision_relevant map (critical)
        -> not_decision_relevant map -> conservative fallback. A pass or an empty
        failure_type is "none"; a judge_error is "none" here (handled elsewhere).
        """
        if not failure_type or failure_type == _JUDGE_ERROR:
            return "none"
        if failure_type == _PROHIBITED:
            return authored_severity or "moderate"
        key = _FAILURE_ALIAS.get(failure_type, failure_type)
        if decision_relevant and key in self.decision_relevant:
            return self.decision_relevant[key]
        if key in self.not_decision_relevant:
            return self.not_decision_relevant[key]
        # Unmapped failure type: never one of the eight triggers (those are all
        # mapped), so cap conservatively rather than silently scoring it "none".
        return "major" if decision_relevant else "moderate"

    def canonical_trigger(self, failure_type: str) -> Optional[str]:
        """The critical-trigger label a failure belongs to, or None. Used for the
        §3.12 per-trigger breakdown the gate report requires."""
        if failure_type == _PROHIBITED:
            return _PROHIBITED
        key = _FAILURE_ALIAS.get(failure_type, failure_type)
        return key if key in self.decision_relevant else None


def load_severity_map(path: str | Path) -> SeverityMap:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return SeverityMap(
        decision_relevant=dict(raw.get("decision_relevant", {})),
        not_decision_relevant=dict(raw.get("not_decision_relevant", {})),
        prohibited_source=raw.get("prohibited_claim_severity_source", "case"),
    )


def decision_relevance_labels(findings) -> dict[tuple[str, str], bool]:
    """Build {(case_id, claim_id): is_decision_relevant} from the judge's
    decision-relevance labels (category in {decision_relevant, background})."""
    labels: dict[tuple[str, str], bool] = {}
    for f in findings:
        if f.category in ("decision_relevant", "background") and f.unit_id is not None:
            labels[(f.case_id, f.unit_id)] = f.category == "decision_relevant"
    return labels


def is_decision_relevant(finding, labels: dict[tuple[str, str], bool]) -> bool:
    """Resolve decision-relevance for one failure finding.

    A finding that self-declares (false_certainty, silent_resolution, critical
    prohibited) is decision-relevant fail-closed. Otherwise, if the judge produced
    a label for this exact claim, use it. Absent a determination, treat as NOT
    decision-relevant: decision-relevance is a positive finding requiring authored
    `decision_relevant_criteria`, and inventing it would fire the hardest gate on
    unlabelled claims. This is why the criteria field is gate-firing (§3.12).
    """
    if finding.decision_relevant:
        return True
    if finding.unit_id is not None:
        return labels.get((finding.case_id, finding.unit_id), False)
    return False


@dataclass
class SeverityVerdict:
    """Derived severity for one failure finding, with the resolution recorded."""

    case_id: str
    section: str
    failure_type: str
    unit_id: Optional[str]
    decision_relevant: bool
    severity: str
    critical_trigger: Optional[str]  # which of the eight fired, or "prohibited_..."

    @property
    def is_critical(self) -> bool:
        return self.severity == "critical"


def derive_severities(findings, severity_map: SeverityMap) -> list[SeverityVerdict]:
    """One SeverityVerdict per FAILURE finding (passes are skipped)."""
    labels = decision_relevance_labels(findings)
    verdicts: list[SeverityVerdict] = []
    for f in findings:
        if f.passed or not f.failure_type or f.failure_type == _JUDGE_ERROR:
            continue
        dr = is_decision_relevant(f, labels)
        sev = severity_map.derive(f.failure_type, dr, authored_severity=f.severity)
        trigger = severity_map.canonical_trigger(f.failure_type) if sev == "critical" else None
        verdicts.append(
            SeverityVerdict(
                case_id=f.case_id,
                section=f.section,
                failure_type=f.failure_type,
                unit_id=f.unit_id,
                decision_relevant=dr,
                severity=sev,
                critical_trigger=trigger,
            )
        )
    return verdicts
