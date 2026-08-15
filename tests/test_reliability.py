"""Phase 6 — evaluate the evaluator (block condition 3.14.5), no network.

Every judge here is a stub with the scorer call signature, so the invariance and
disagreement machinery is exercised without a live judge. The tests pin the
behaviours a release leans on:

  - perturbations preserve meaning (claim_ids, the claim->document join) and never
    mutate the baseline record;
  - a judge that flips on a meaning-preserving perturbation is caught, and the
    flip rate is what gate 5 consumes;
  - a stable judge yields zero flips;
  - judge outages are excluded from the flip denominator, not counted as agreement;
  - the judge-vs-reference audit reports disagreement rather than resolving it.
"""

from __future__ import annotations

from barn_eval.aggregation.gates import FAIL, NOT_EVALUATED, PASS, evaluate_gates, load_thresholds
from barn_eval.harness.models import EvaluationRecord
from barn_eval.judge.client import JudgeError, JudgeVerdict
from barn_eval.reliability import (
    audit_groundedness,
    default_perturbations,
    run_invariance,
)
from barn_eval.reliability.perturbations import (
    citation_format,
    claim_order,
    paraphrase,
    whitespace,
)
from barn_eval.scorers.base import Finding
from barn_eval.scorers.judge.groundedness import GroundednessScorer

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
THR = load_thresholds(ROOT / "configs/thresholds.yaml")


# --- helpers ----------------------------------------------------------------

def _doc(source_id, content):
    return {
        "source_id": source_id, "content": content, "content_hash": "x",
        "source_authority": "E2", "is_distractor": False, "subject_patient_id": "synth_001",
        "retrieval_score": 0.9, "source_version": "final", "source_date": "2026-06-30",
    }


def _claim(cid, text, citations):
    return {"claim_id": cid, "text": text, "citations": citations, "asserted_authority": None}


def _record(claims, docs):
    case = {
        "case_id": "t1", "case_type": "clean", "adversarial_category": None,
        "input": {"user_question": "q", "patient_context": {"patient_id": "synth_001"},
                  "retrieved_documents": docs},
        "gold": {"expected_behavior": "answer"},
    }
    resp = {"case_id": "t1", "answer_text": " ".join(c["text"] for c in claims),
            "abstained": False, "abstention": None, "claims": claims}
    return EvaluationRecord(case=case, response=resp, confirmations=[], status="ok")


class Stub:
    """Constant verdict for every call (a perfectly stable judge)."""

    def __init__(self, data):
        self.data = data

    def __call__(self, prompt_name, payload):
        return JudgeVerdict(data=self.data, model="stub", prompt_name=prompt_name, prompt_version="v1")


class FlipsOnWhitespace:
    """An UNSTABLE judge: verdict depends on a purely formatting detail (a trailing
    period the whitespace perturbation adds). Simulates a judge keying off surface."""

    def __call__(self, prompt_name, payload):
        text = payload.get("claim_text", "")
        cat = "unsupported" if text.rstrip().endswith(".") else "grounded"
        return JudgeVerdict(data={"category": cat}, model="stub", prompt_name=prompt_name, prompt_version="v1")


class Boom:
    def __call__(self, prompt_name, payload):
        raise JudgeError("simulated outage")


# --- perturbations preserve meaning -----------------------------------------

def test_claim_order_reorders_but_keeps_ids_and_does_not_mutate_baseline():
    rec = _record([_claim("c1", "alpha", ["d"]), _claim("c2", "beta", ["d"])], [_doc("d", "x")])
    out = claim_order(rec, seed=3)
    assert [c["claim_id"] for c in rec.claims] == ["c1", "c2"]          # baseline untouched
    assert sorted(c["claim_id"] for c in out.claims) == ["c1", "c2"]    # same units, some order


def test_citation_format_rewrites_both_sides_so_the_join_survives():
    rec = _record([_claim("c1", "x", ["doc_a"])], [_doc("doc_a", "content")])
    out = citation_format(rec)
    assert out.claims[0]["citations"] == ["DOC_A"]
    assert out.retrieved_documents[0]["source_id"] == "DOC_A"
    # the claim still resolves to its document (id present on both sides)
    assert out.claims[0]["citations"][0] in out.documents_by_id
    assert rec.claims[0]["citations"] == ["doc_a"]  # baseline untouched


def test_paraphrase_and_whitespace_hold_claim_ids():
    rec = _record([_claim("c1", "the patient is not stable", ["d"])], [_doc("d", "x")])
    p = paraphrase(rec)
    w = whitespace(rec)
    assert p.claims[0]["claim_id"] == "c1" and w.claims[0]["claim_id"] == "c1"
    assert p.claims[0]["text"] != rec.claims[0]["text"]   # something actually changed
    assert "isn't" in p.claims[0]["text"] or "this patient" in p.claims[0]["text"]


# --- invariance: flip detection ---------------------------------------------

def test_stable_judge_has_zero_flip_rate():
    rec = _record([_claim("c1", "grounded claim", ["d"])], [_doc("d", "content")])
    scorers = [GroundednessScorer(Stub({"category": "grounded"}))]
    report = run_invariance([rec], scorers)
    assert report.n_compared == 4        # 4 perturbations x 1 comparable unit
    assert report.verdict_flip_rate == 0.0
    assert report.gate_input() == 0.0


def test_unstable_judge_is_caught_and_only_by_the_perturbation_that_moves_it():
    rec = _record([_claim("c1", "grounded claim", ["d"])], [_doc("d", "content")])
    scorers = [GroundednessScorer(FlipsOnWhitespace())]
    report = run_invariance([rec], scorers, perturbations=default_perturbations())
    by_name = {p.name: p for p in report.per_perturbation}
    # whitespace appends a period -> the stub flips grounded->unsupported
    assert by_name["whitespace"].flip_count == 1
    # claim_order/citation_format leave the trailing punctuation alone -> no flip
    assert by_name["claim_order"].flip_count == 0
    assert report.n_flips >= 1 and report.verdict_flip_rate > 0.0


def test_judge_errors_are_excluded_from_the_flip_denominator():
    rec = _record([_claim("c1", "x", ["d"])], [_doc("d", "content")])
    scorers = [GroundednessScorer(Boom())]
    report = run_invariance([rec], scorers)
    assert report.n_compared == 0            # every unit was an outage on both sides
    assert report.judge_errors_excluded == 4  # 4 perturbations
    assert report.gate_input() is None        # -> gate 5 stays NOT_EVALUATED, not a fake 0.0


# --- judge-vs-reference disagreement ----------------------------------------

def test_disagreement_uses_the_real_groundability_audit():
    audit = [
        {"audit_id": "a1", "source": "s", "user_question": "q", "claim_text": "t",
         "cited_documents": [], "gold_category": "grounded", "gold_subtype": None},
        {"audit_id": "a2", "source": "s", "user_question": "q", "claim_text": "t",
         "cited_documents": [], "gold_category": "unsupported", "gold_subtype": None},
    ]
    # judge always says grounded: agrees on a1, disagrees on a2.
    rep = audit_groundedness(Stub({"category": "grounded"}), audit)
    assert rep.n == 2 and rep.agreements == 1
    assert rep.disagreement_rate == 0.5
    assert rep.to_dict()["mismatches"][0]["audit_id"] == "a2"


def test_disagreement_excludes_outages_from_its_denominator():
    audit = [{"audit_id": "a1", "source": "s", "user_question": "q", "claim_text": "t",
              "cited_documents": [], "gold_category": "grounded", "gold_subtype": None}]
    rep = audit_groundedness(Boom(), audit)
    assert rep.judge_errors == 1 and rep.n == 0 and rep.disagreement_rate == 0.0


# --- gate 5 consumes the flip rate ------------------------------------------

def test_flip_rate_drives_gate5():
    base = [Finding(section="correctness", failure_type="", passed=True, case_id="A")]
    # None -> not evaluated; a nonzero flip rate -> gate 5 fails (max is 0.0)
    from barn_eval.aggregation import load_severity_map
    sev = load_severity_map(ROOT / "configs/severity_map.yaml")
    assert evaluate_gates(base, n_cases=1, severity_map=sev, thresholds=THR).by_gate(5).status == NOT_EVALUATED
    assert evaluate_gates(base, n_cases=1, severity_map=sev, thresholds=THR, evaluator_flip_rate=0.0).by_gate(5).status == PASS
    assert evaluate_gates(base, n_cases=1, severity_map=sev, thresholds=THR, evaluator_flip_rate=0.25).by_gate(5).status == FAIL
