"""4.6 latency and estimated inference cost.

Broken out by case type (clean vs adversarial, answered vs abstained), since
abstention and safety-check paths may have different profiles.

Both fields are self-reported by the system under test. Where the harness does
not measure wall-clock time itself these figures are attested, not observed, and
are labelled as such in the report.
"""

from __future__ import annotations

from ..base import Finding, Scorer


class CostScorer(Scorer):
    """4.6 latency + cost, tagged by case type and answer path. Self-reported (attested)."""

    section = "latency-cost"
    deterministic = True

    def score(self, record) -> list[Finding]:
        if record.is_missing:
            return []

        resp = record.response or {}
        # answered / abstained partition; clean / adversarial partition.
        path = "abstained" if record.abstained else "answered"
        bucket = {
            "case_type": record.case_type,
            "path": path,
            "attested": True,  # self-reported, not harness-measured
        }

        findings = [
            Finding(
                section="latency-cost",
                failure_type="",
                passed=True,
                unit_id="latency_ms",
                case_id=record.case_id,
                value=self._num(resp.get("latency_ms")),
                rationale="self-reported latency (attested, not harness-observed)",
                evidence=bucket,
            ),
            Finding(
                section="latency-cost",
                failure_type="",
                passed=True,
                unit_id="estimated_cost_usd",
                case_id=record.case_id,
                value=self._num(resp.get("estimated_cost_usd")),
                rationale="self-reported estimated inference cost (attested)",
                evidence=bucket,
            ),
        ]
        return findings

    @staticmethod
    def _num(v):
        return float(v) if isinstance(v, (int, float)) else None
