"""Rate computation. Pooled and per-case-averaged, for every rate metric.

Per-case-averaged is the primary safety-facing number: it surfaces single bad
cases more aggressively than a pooled figure can, because pooling lets a large
well-behaved case dilute a small catastrophic one.

Contains no gate logic. See gates.py for why that separation is physical. A rate
is arithmetic over a stream of Findings: the denominator is the units that count
(`counts_denominator` and not a missing response), the numerator is the failures
among them. This module never decides whether a rate is acceptable.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field


@dataclass
class MetricRate:
    """One metric's pooled and per-case-averaged failure rate.

    pooled     Σ failures / Σ denominator units, across the whole suite
    per_case   mean over cases of (failures / denominator) within each case
    Both are reported: pooled is the headline, per_case is the safety-facing
    number that refuses to let one big clean case dilute a small broken one.
    """

    metric: str
    numerator: int
    denominator: int
    n_cases: int
    per_case: float
    by_failure_type: dict[str, int] = field(default_factory=dict)

    @property
    def pooled(self) -> float:
        return (self.numerator / self.denominator) if self.denominator else 0.0


def _is_counted(f) -> bool:
    """A finding is in a denominator iff it opts in and is not an evaluator outage."""
    return f.counts_denominator and f.failure_type != "judge_error"


def rate_over(findings, *, metric: str) -> MetricRate:
    """Pool + per-case a single already-filtered finding list into one MetricRate."""
    counted = [f for f in findings if _is_counted(f)]
    numerator = sum(1 for f in counted if f.is_failure)
    denominator = len(counted)

    per_case_num: dict[str, int] = defaultdict(int)
    per_case_den: dict[str, int] = defaultdict(int)
    for f in counted:
        per_case_den[f.case_id] += 1
        if f.is_failure:
            per_case_num[f.case_id] += 1
    case_rates = [per_case_num[c] / per_case_den[c] for c in per_case_den]
    per_case = sum(case_rates) / len(case_rates) if case_rates else 0.0

    by_type = Counter(f.failure_type for f in counted if f.is_failure and f.failure_type)

    return MetricRate(
        metric=metric,
        numerator=numerator,
        denominator=denominator,
        n_cases=len(per_case_den),
        per_case=per_case,
        by_failure_type=dict(by_type),
    )


def compute_rates(findings) -> dict[str, MetricRate]:
    """One MetricRate per metric `section` present in the stream.

    Grouping by section keeps each Part One clause its own denominator (e.g. 3.5
    fabricated citations are pooled over claims, 4.3 recall over required docs),
    which is what stops unrelated units being averaged into one another.
    """
    by_section: dict[str, list] = defaultdict(list)
    for f in findings:
        by_section[f.section].append(f)
    return {section: rate_over(fs, metric=section) for section, fs in sorted(by_section.items())}


def case_failure_rate(findings, predicate, *, n_cases: int) -> tuple[int, float]:
    """Fraction of cases with >=1 failure matching `predicate`.

    Denominator is the total number of cases evaluated (passed in, because a case
    with no findings for a metric still counts), not the number that produced a
    finding - a metric measured "per case evaluated" (like the §3.12 critical
    safety failure rate) must not shrink its own denominator to the cases it fired
    on. Returns (n_cases_hit, rate).
    """
    hit = {f.case_id for f in findings if predicate(f)}
    rate = (len(hit) / n_cases) if n_cases else 0.0
    return len(hit), rate
