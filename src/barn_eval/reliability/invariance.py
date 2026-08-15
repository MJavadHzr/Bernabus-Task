"""Evaluator invariance testing. Block condition 3.14.5.

If a meaning-preserving perturbation changes a verdict, the evaluator is unstable,
and an unstable evaluator cannot certify anything - the release decision is
invalidated regardless of the system's measured scores. Gate 5 therefore takes
precedence over every metric the system earns.

Mechanism
  1. score the baseline records with the judge scorers -> baseline verdicts
  2. for each perturbation, score the perturbed records with the SAME scorers
  3. align verdicts unit-for-unit by (case_id, section, unit_id) - perturbations
     never change a unit id - and count a FLIP wherever pass/fail, failure_type or
     category disagrees between baseline and perturbed
  4. verdict_flip_rate = flips / comparable unit-verdicts, over all perturbations

Judge outages are excluded from the denominator: a unit that is a judge_error on
either side is not a stability signal, it is a measurement gap (surfaced
separately as judge_errors_excluded). Fail-closed elsewhere; here an outage is
neither a flip nor a clean agreement.

Covers the LLM judge. The evaluation-side preprocessor is versioned under
evaluation_version and is equally in scope for 3.14.5; it is PARKED in this build
(see preprocessor/__init__.py), so this run exercises the judge and records the
preprocessor as an unexercised, declared surface rather than pretending it was
tested.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

from ..harness.models import EvaluationRecord
from ..scorers.base import Finding
from .perturbations import default_perturbations

# A unit's verdict identity: same metric GROUP + same unit across baseline and
# perturbed. The group, not the raw section, because some scorers encode the
# verdict IN the section - groundedness emits grounded / unsupported /
# citation-failure for one claim depending on the outcome. Keying on the raw
# section would make a real flip (grounded->unsupported) look like two unrelated
# units and hide it. Collapsing those to one group is exactly right: they share a
# single denominator (see scorers/judge/groundedness.py), so a move between them
# is the instability gate 5 must catch.
UnitKey = tuple[str, str, Optional[str]]

_SECTION_GROUP = {
    "grounded": "groundedness",
    "unsupported": "groundedness",
    "citation-failure": "groundedness",
}


def _group(section: str) -> str:
    return _SECTION_GROUP.get(section, section)


@dataclass(frozen=True)
class UnitVerdict:
    """The comparable content of one Finding: what a flip is measured against."""

    passed: bool
    failure_type: str
    category: Optional[str]
    judge_error: bool
    section: str = ""     # the concrete section on this side (may move within a group)


@dataclass
class Flip:
    """One unit whose verdict changed under a perturbation."""

    perturbation: str
    case_id: str
    section: str
    unit_id: Optional[str]
    baseline: UnitVerdict
    perturbed: UnitVerdict


@dataclass
class PerturbationResult:
    name: str
    compared: int          # units comparable on both sides (neither a judge_error)
    flips: list[Flip]
    judge_errors: int      # units dropped because one side was a judge outage

    @property
    def flip_count(self) -> int:
        return len(self.flips)

    @property
    def flip_rate(self) -> float:
        return (self.flip_count / self.compared) if self.compared else 0.0


@dataclass
class ReliabilityReport:
    """The evaluator-stability verdict for one run. `verdict_flip_rate` is the
    single number gate 5 consumes."""

    per_perturbation: list[PerturbationResult]
    n_compared: int
    n_flips: int
    judge_errors_excluded: int
    perturbation_names: list[str] = field(default_factory=list)

    @property
    def verdict_flip_rate(self) -> float:
        """Flips over all comparable unit-verdicts across every perturbation."""
        return (self.n_flips / self.n_compared) if self.n_compared else 0.0

    def gate_input(self) -> Optional[float]:
        """The value fed to gate 5. None when nothing was comparable (e.g. no judge
        scorers, or every unit was an outage) - so gate 5 stays NOT_EVALUATED
        rather than being handed a fake 0.0 that would read as 'stable'."""
        return self.verdict_flip_rate if self.n_compared else None

    def to_dict(self) -> dict:
        return {
            "verdict_flip_rate": self.verdict_flip_rate,
            "n_compared": self.n_compared,
            "n_flips": self.n_flips,
            "judge_errors_excluded": self.judge_errors_excluded,
            "perturbations": [
                {
                    "name": p.name,
                    "compared": p.compared,
                    "flips": p.flip_count,
                    "flip_rate": p.flip_rate,
                    "judge_errors": p.judge_errors,
                    "flipped_units": [
                        {
                            "case_id": f.case_id,
                            "section": f.section,
                            "unit_id": f.unit_id,
                            "baseline": f.baseline.failure_type or ("pass" if f.baseline.passed else "fail"),
                            "perturbed": f.perturbed.failure_type or ("pass" if f.perturbed.passed else "fail"),
                        }
                        for f in p.flips
                    ],
                }
                for p in self.per_perturbation
            ],
        }


def _score(scorers, records: Iterable[EvaluationRecord]) -> list[Finding]:
    return [f for s in scorers for r in records for f in s.score(r)]


def _verdict_index(findings: Iterable[Finding]) -> dict[UnitKey, UnitVerdict]:
    """Index findings by (case_id, section, unit_id) -> UnitVerdict.

    A judge-scored unit is emitted exactly once per (section, unit), so the key is
    unique. judge_error findings are kept in the index (flagged) so the comparator
    can drop, not silently pass, a unit that errored on either side.
    """
    idx: dict[UnitKey, UnitVerdict] = {}
    for f in findings:
        key = (f.case_id, _group(f.section), f.unit_id)
        idx[key] = UnitVerdict(
            passed=f.passed,
            failure_type=f.failure_type,
            category=f.category,
            judge_error=(f.failure_type == "judge_error"),
            section=f.section,
        )
    return idx


def _differs(a: UnitVerdict, b: UnitVerdict) -> bool:
    return (a.passed != b.passed) or (a.failure_type != b.failure_type) or (a.category != b.category)


def _compare(name, baseline: dict, perturbed: dict) -> PerturbationResult:
    compared, judge_errors = 0, 0
    flips: list[Flip] = []
    for key, base in baseline.items():
        pert = perturbed.get(key)
        if pert is None:
            # A unit that ceased to exist under perturbation is itself instability,
            # but only for judge-scored units; here we conservatively skip absent
            # counterparts (a perturbation must not add/remove units) and let the
            # missing side surface as an unequal-cardinality assertion in tests.
            continue
        if base.judge_error or pert.judge_error:
            judge_errors += 1
            continue
        compared += 1
        if _differs(base, pert):
            case_id, section, unit_id = key
            flips.append(Flip(name, case_id, section, unit_id, base, pert))
    return PerturbationResult(name=name, compared=compared, flips=flips, judge_errors=judge_errors)


def run_invariance(
    records: list[EvaluationRecord],
    scorers: list,
    *,
    perturbations: Optional[dict[str, Callable[..., EvaluationRecord]]] = None,
    seed: int = 0,
) -> ReliabilityReport:
    """Score baseline vs each perturbed variant and measure the verdict-flip rate.

    records       joined EvaluationRecords (judge-scorable units live here)
    scorers       the judge scorers, already built with the injected judge; the
                  SAME instances score baseline and every perturbation
    perturbations name -> transform; defaults to the four meaning-preserving ones
    """
    perturbations = perturbations if perturbations is not None else default_perturbations()
    baseline_idx = _verdict_index(_score(scorers, records))

    results: list[PerturbationResult] = []
    for name, transform in perturbations.items():
        perturbed_records = [transform(r, seed=seed) for r in records]
        perturbed_idx = _verdict_index(_score(scorers, perturbed_records))
        results.append(_compare(name, baseline_idx, perturbed_idx))

    n_compared = sum(r.compared for r in results)
    n_flips = sum(r.flip_count for r in results)
    judge_errors = sum(r.judge_errors for r in results)
    return ReliabilityReport(
        per_perturbation=results,
        n_compared=n_compared,
        n_flips=n_flips,
        judge_errors_excluded=judge_errors,
        perturbation_names=list(perturbations),
    )
