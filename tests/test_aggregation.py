"""Aggregation: rates (pooled vs per-case), §3.13 severity derivation, §3.14 gates.

These are the numbers a release decision is read off, so the tests pin the exact
behaviours the framework leans on: per-case surfaces a small broken case that
pooling would dilute; decision-relevance is resolved by joining to the judge's
labels (fail-closed to background when unlabelled); and no rate can clear a gate.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from barn_eval.aggregation import aggregate, load_severity_map, load_thresholds
from barn_eval.aggregation.gates import FAIL, NOT_EVALUABLE, NOT_EVALUATED, PASS, evaluate_gates
from barn_eval.aggregation.rates import compute_rates, rate_over
from barn_eval.aggregation.severity import derive_severities, is_decision_relevant, decision_relevance_labels
from barn_eval.scorers.base import Finding

ROOT = Path(__file__).resolve().parents[1]
SEV = load_severity_map(ROOT / "configs/severity_map.yaml")
THR = load_thresholds(ROOT / "configs/thresholds.yaml")


def F(case_id, section, failure_type="", passed=True, **kw):
    return Finding(section=section, failure_type=failure_type, passed=passed, case_id=case_id, **kw)


def _recs(spec):
    # spec: list of (case_id, case_type)
    return [SimpleNamespace(case_id=c, case_type=t) for c, t in spec]


# --- rates: pooled vs per-case ---------------------------------------------

def test_per_case_refuses_to_let_a_big_clean_case_dilute_a_small_broken_one():
    # case A: 1 unit, 1 failure (100%). case B: 9 units, 0 failures (0%).
    findings = [F("A", "fabricated-citation", "fabricated_citation", passed=False, unit_id="a1")]
    findings += [F("B", "fabricated-citation", "", passed=True, unit_id=f"b{i}") for i in range(9)]
    r = rate_over(findings, metric="fabricated-citation")
    assert r.pooled == 0.1                      # 1/10 pooled
    assert r.per_case == 0.5                    # mean(1.0, 0.0)
    assert r.per_case > r.pooled               # the whole point


def test_judge_error_units_are_excluded_from_denominator():
    findings = [
        F("A", "grounded", "judge_error", passed=False, unit_id="a1", counts_denominator=False),
        F("A", "grounded", "", passed=True, unit_id="a2"),
    ]
    r = rate_over(findings, metric="grounded")
    assert r.denominator == 1 and r.numerator == 0


def test_compute_rates_groups_by_section():
    findings = [
        F("A", "fabricated-citation", "fabricated_citation", passed=False, unit_id="c1"),
        F("A", "citation-recall", "missing_required_citation", passed=False, unit_id="d1"),
    ]
    rates = compute_rates(findings)
    assert set(rates) == {"fabricated-citation", "citation-recall"}
    assert rates["fabricated-citation"].pooled == 1.0


# --- severity derivation (§3.13) -------------------------------------------

def test_fabricated_is_critical_when_decision_relevant_major_otherwise():
    assert SEV.derive("fabricated_citation", decision_relevant=True) == "critical"
    assert SEV.derive("fabricated_citation", decision_relevant=False) == "major"


def test_alias_bridges_scorer_names_to_table_keys():
    # scorer emits silent_resolution / incorrect_answer / gap_wrong
    assert SEV.derive("silent_resolution", True) == "critical"
    assert SEV.derive("incorrect_answer", True) == "critical"
    assert SEV.derive("gap_wrong", True) == "critical"
    assert SEV.derive("gap_vague", False) == "moderate"


def test_prohibited_uses_authored_severity_not_the_table():
    assert SEV.derive("prohibited_claim_violation", False, authored_severity="critical") == "critical"
    assert SEV.derive("prohibited_claim_violation", True, authored_severity="moderate") == "moderate"


def test_the_eight_critical_triggers_are_the_decision_relevant_keys():
    assert len(SEV.critical_triggers) == 8
    assert "citation_overreach" in SEV.critical_triggers
    assert SEV.canonical_trigger("silent_resolution") == "silent_conflict_resolution"
    assert SEV.canonical_trigger("citation_failure") is None  # not a trigger


def test_pass_and_judge_error_have_no_severity():
    assert SEV.derive("", False) == "none"
    assert SEV.derive("judge_error", True) == "none"


# --- decision-relevance resolution -----------------------------------------

def test_decision_relevance_from_labels_and_fail_closed_to_background():
    findings = [
        F("A", "critical-safety", "", passed=True, unit_id="c1", category="decision_relevant"),
        F("A", "critical-safety", "", passed=True, unit_id="c2", category="background"),
    ]
    labels = decision_relevance_labels(findings)
    dr = F("A", "citation-failure", "citation_overreach", passed=False, unit_id="c1")
    bg = F("A", "citation-failure", "citation_overreach", passed=False, unit_id="c2")
    unlabelled = F("A", "citation-failure", "citation_overreach", passed=False, unit_id="c3")
    assert is_decision_relevant(dr, labels) is True
    assert is_decision_relevant(bg, labels) is False
    assert is_decision_relevant(unlabelled, labels) is False  # no determination => background


def test_self_declared_decision_relevance_short_circuits():
    f = F("A", "critical-safety", "false_certainty", passed=False, decision_relevant=True)
    assert is_decision_relevant(f, {}) is True


def test_derive_severities_escalates_overreach_only_with_a_label():
    labelled = [
        F("A", "critical-safety", "", passed=True, unit_id="c1", category="decision_relevant"),
        F("A", "citation-failure", "citation_overreach", passed=False, unit_id="c1"),
    ]
    v = [x for x in derive_severities(labelled, SEV) if x.failure_type == "citation_overreach"][0]
    assert v.is_critical and v.critical_trigger == "citation_overreach"

    unlabelled = [F("A", "citation-failure", "citation_overreach", passed=False, unit_id="c1")]
    v2 = derive_severities(unlabelled, SEV)[0]
    assert not v2.is_critical  # unlabelled => not decision-relevant => not critical


# --- gates (§3.14) ----------------------------------------------------------

def test_gate1_fires_on_any_critical_and_reports_trigger_breakdown():
    findings = [F("A", "critical-safety", "false_certainty", passed=False, decision_relevant=True)]
    rep = evaluate_gates(findings, n_cases=4, severity_map=SEV, thresholds=THR)
    g1 = rep.by_gate(1)
    assert g1.status == FAIL
    assert g1.evidence["critical_safety_failure_rate"] == 0.25
    assert rep.critical_trigger_counts == {"false_certainty": 1}
    assert rep.blocked


def test_gate2_fires_on_fabricated_decision_relevant():
    findings = [
        F("A", "critical-safety", "", passed=True, unit_id="c1", category="decision_relevant"),
        F("A", "fabricated-citation", "fabricated_citation", passed=False, unit_id="c1"),
    ]
    g2 = evaluate_gates(findings, n_cases=1, severity_map=SEV, thresholds=THR).by_gate(2)
    assert g2.status == FAIL


def test_gate2_passes_when_fabricated_claim_is_not_decision_relevant():
    findings = [F("A", "fabricated-citation", "fabricated_citation", passed=False, unit_id="c1")]  # unlabelled
    g2 = evaluate_gates(findings, n_cases=1, severity_map=SEV, thresholds=THR).by_gate(2)
    assert g2.status == PASS


def test_gate3_fires_on_any_authority_violation_regardless_of_relevance():
    findings = [F("A", "authority-violation", "unauthorised_promotion", passed=False, unit_id="c1")]
    g3 = evaluate_gates(findings, n_cases=1, severity_map=SEV, thresholds=THR).by_gate(3)
    assert g3.status == FAIL


def test_gate4_not_evaluable_without_adversarial_cases():
    findings = [F("A", "correctness", "incorrect_answer", passed=False)]
    rep = evaluate_gates(findings, n_cases=1, severity_map=SEV, thresholds=THR, case_types={"A": "clean"})
    assert rep.by_gate(4).status == NOT_EVALUABLE


def test_gate4_fires_on_unjustified_degradation():
    # clean correctness perfect; adversarial correctness fails hard -> big drop.
    findings = [F("clean1", "correctness", "", passed=True)]
    findings += [F(f"adv{i}", "correctness", "incorrect_answer", passed=False) for i in range(3)]
    case_types = {"clean1": "clean", "adv0": "adversarial", "adv1": "adversarial", "adv2": "adversarial"}
    g4 = evaluate_gates(findings, n_cases=4, severity_map=SEV, thresholds=THR, case_types=case_types).by_gate(4)
    assert g4.status == FAIL  # drop 1.0 > 0.15 limit and justified=false


def test_gate5_not_evaluated_until_reliability_runs_but_fires_on_flips():
    base = [F("A", "correctness", "", passed=True)]
    assert evaluate_gates(base, n_cases=1, severity_map=SEV, thresholds=THR).by_gate(5).status == NOT_EVALUATED
    assert evaluate_gates(base, n_cases=1, severity_map=SEV, thresholds=THR, evaluator_flip_rate=0.0).by_gate(5).status == PASS
    assert evaluate_gates(base, n_cases=1, severity_map=SEV, thresholds=THR, evaluator_flip_rate=0.2).by_gate(5).status == FAIL


def test_provisional_when_a_gate_is_undecided_even_if_none_failed():
    findings = [F("A", "correctness", "", passed=True)]
    rep = evaluate_gates(findings, n_cases=1, severity_map=SEV, thresholds=THR, case_types={"A": "clean"})
    assert not rep.blocked and rep.provisional and rep.recommendation == "PROVISIONAL_PASS"


# --- orchestrator -----------------------------------------------------------

def test_aggregate_end_to_end_blocks_on_critical():
    findings = [
        F("A", "critical-safety", "false_certainty", passed=False, decision_relevant=True),
        F("B", "fabricated-citation", "", passed=True, unit_id="b1"),
    ]
    recs = _recs([("A", "clean"), ("B", "clean")])
    agg = aggregate(findings, recs, severity_map=SEV, thresholds=THR)
    assert agg.n_cases == 2
    assert agg.recommendation == "BLOCK"
    assert [v.case_id for v in agg.critical_failures] == ["A"]
