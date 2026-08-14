"""Rates, severity derivation and release gates.

`aggregate()` is the one entrypoint the runner calls: it turns a flat stream of
Findings (plus the records, for case count and clean/adversarial partition) into
rates + derived severities + a gate report, without ever letting an average touch
a gate. rates.py stays pure arithmetic; severity.py derives §3.13 tiers; gates.py
decides §3.14 - three files so the "no average clears a gate" boundary is physical.
"""

from __future__ import annotations

from dataclasses import dataclass

from .gates import GateReport, GateResult, evaluate_gates, load_thresholds
from .rates import MetricRate, case_failure_rate, compute_rates, rate_over
from .severity import (
    SeverityMap,
    SeverityVerdict,
    derive_severities,
    load_severity_map,
)

__all__ = [
    "aggregate",
    "AggregateResult",
    "compute_rates",
    "rate_over",
    "case_failure_rate",
    "MetricRate",
    "load_severity_map",
    "derive_severities",
    "SeverityMap",
    "SeverityVerdict",
    "evaluate_gates",
    "load_thresholds",
    "GateReport",
    "GateResult",
]


@dataclass
class AggregateResult:
    """Everything a report needs from one run's findings."""

    rates: dict[str, MetricRate]
    severities: list[SeverityVerdict]
    gates: GateReport
    n_cases: int

    @property
    def recommendation(self) -> str:
        return self.gates.recommendation

    @property
    def critical_failures(self) -> list[SeverityVerdict]:
        return [v for v in self.severities if v.is_critical]


def aggregate(
    findings,
    records,
    *,
    severity_map: SeverityMap,
    thresholds: dict,
    evaluator_flip_rate: float | None = None,
) -> AggregateResult:
    """Fold a run's findings into rates + severities + gates.

    `records` is the joined EvaluationRecord list: it fixes the case denominator
    (every case counts, including missing responses) and the clean/adversarial
    partition gate 4 needs. Nothing here is inferred from the findings' own
    coverage, so a metric that fired on no case still has the right denominator.
    """
    n_cases = len(records)
    case_types = {r.case_id: r.case_type for r in records}
    return AggregateResult(
        rates=compute_rates(findings),
        severities=derive_severities(findings, severity_map),
        gates=evaluate_gates(
            findings,
            n_cases=n_cases,
            severity_map=severity_map,
            thresholds=thresholds,
            case_types=case_types,
            evaluator_flip_rate=evaluator_flip_rate,
        ),
        n_cases=n_cases,
    )
