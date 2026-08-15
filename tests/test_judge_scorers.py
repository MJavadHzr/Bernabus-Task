"""Judge-scorer plumbing on hand-built minimal records, with stub judges.

These assert the mapping from a judge verdict to Findings: categories, failure
types, fail-closed defaults on an unparseable verdict, and the judge_error path
when the judge raises. No network; every judge is a stub.
"""

from __future__ import annotations

from barn_eval.harness.models import EvaluationRecord
from barn_eval.judge.client import JudgeError, JudgeVerdict
from barn_eval.scorers.judge.conflict import ConflictHandlingScorer
from barn_eval.scorers.judge.correctness import CorrectnessScorer
from barn_eval.scorers.judge.decision_relevance import DecisionRelevanceScorer
from barn_eval.scorers.judge.gap_specificity import GapSpecificityScorer
from barn_eval.scorers.judge.groundedness import GroundednessScorer
from barn_eval.scorers.judge.injection import InjectionResistanceScorer
from barn_eval.scorers.judge.staleness import StalenessHandlingScorer


class Stub:
    """Returns a fixed verdict dict for every call."""

    def __init__(self, data):
        self.data = data

    def __call__(self, prompt_name, payload):
        return JudgeVerdict(data=self.data, model="stub", prompt_name=prompt_name, prompt_version="v1")


class Boom:
    def __call__(self, prompt_name, payload):
        raise JudgeError("simulated judge outage")


def _doc(source_id, content="c", subject="synth_001", **kw):
    d = {
        "source_id": source_id, "content": content, "content_hash": "x",
        "source_authority": "E2", "is_distractor": False, "subject_patient_id": subject,
        "retrieval_score": 0.9, "source_version": "final", "source_date": "2026-06-30",
    }
    d.update(kw)
    return d


def _case(docs, gold, adv=None):
    return {
        "case_id": "t1", "case_type": "clean", "adversarial_category": adv,
        "input": {"user_question": "q", "patient_context": {"patient_id": "synth_001"}, "retrieved_documents": docs},
        "gold": gold,
    }


def _resp(claims, abstained=False, abstention=None):
    return {
        "case_id": "t1", "answer_text": " ".join(c["text"] for c in claims),
        "abstained": abstained, "abstention": abstention, "claims": claims,
    }


def _rec(case, resp, confs=None):
    return EvaluationRecord(case=case, response=resp, confirmations=confs or [], status="ok")


def _claim(cid, text, citations):
    return {"claim_id": cid, "text": text, "citations": citations, "asserted_authority": None}


# --- 3.1 correctness --------------------------------------------------------

def test_correctness_correct_and_incorrect():
    case = _case([_doc("d")], {"expected_behavior": "answer", "expected_conclusion": "stable"})
    resp = _resp([_claim("c1", "it is stable", ["d"])])
    ok = CorrectnessScorer(Stub({"correct": True, "rationale": "r"})).score(_rec(case, resp))
    assert ok and ok[0].passed
    bad = CorrectnessScorer(Stub({"correct": False, "rationale": "r"})).score(_rec(case, resp))
    assert bad and bad[0].is_failure and bad[0].failure_type == "incorrect_answer"


def test_correctness_skips_without_gold_conclusion():
    case = _case([_doc("d")], {"expected_behavior": "answer"})
    assert CorrectnessScorer(Stub({"correct": True})).score(_rec(case, _resp([_claim("c1", "x", ["d"])]))) == []


# --- 3.2/3.3/3.4 groundedness ----------------------------------------------

def test_groundedness_unsupported():
    case = _case([_doc("d")], {"expected_behavior": "answer"})
    resp = _resp([_claim("c1", "invented", ["d"])])
    f = GroundednessScorer(Stub({"category": "unsupported", "rationale": "r"})).score(_rec(case, resp))
    assert f and f[0].is_failure and f[0].failure_type == "unsupported_claim" and f[0].section == "unsupported"


def test_groundedness_wrong_source_vs_overreach_split():
    case = _case([_doc("d")], {"expected_behavior": "answer"})
    resp = _resp([_claim("c1", "x", ["d"])])
    ws = GroundednessScorer(Stub({"category": "citation_failure", "citation_failure_subtype": "wrong_source"})).score(_rec(case, resp))
    assert ws[0].failure_type == "citation_failure"
    ov = GroundednessScorer(Stub({"category": "citation_failure", "citation_failure_subtype": "overreach"})).score(_rec(case, resp))
    assert ov[0].failure_type == "citation_overreach"


def test_groundedness_skips_on_abstention():
    case = _case([_doc("d")], {"expected_behavior": "abstain", "expected_abstention": {"reason_type": "missing_evidence", "expected_gap_elements": ["x"]}})
    resp = _resp([], abstained=True, abstention={"reason_type": "missing_evidence"})
    assert GroundednessScorer(Stub({"category": "grounded"})).score(_rec(case, resp)) == []


# --- 3.12 decision relevance ------------------------------------------------

def test_decision_relevance_labels_not_fails():
    case = _case([_doc("d")], {"expected_behavior": "answer", "decision_relevant_criteria": ["about X"]})
    resp = _resp([_claim("c1", "x", ["d"])])
    f = DecisionRelevanceScorer(Stub({"decision_relevant": True, "matched_criterion": "about X"})).score(_rec(case, resp))
    assert f and f[0].passed and f[0].decision_relevant and f[0].category == "decision_relevant"


def test_decision_relevance_skips_without_criteria():
    case = _case([_doc("d")], {"expected_behavior": "answer"})
    assert DecisionRelevanceScorer(Stub({"decision_relevant": True})).score(_rec(case, _resp([_claim("c1", "x", ["d"])]))) == []


# --- 3.8 gap specificity ----------------------------------------------------

def _abstain_case():
    return _case([_doc("d")], {"expected_behavior": "abstain", "expected_abstention": {"reason_type": "missing_evidence", "expected_gap_elements": ["ALT result"], "red_herring_elements": ["blood pressure"]}})


def test_gap_specificity_correct_wrong_vague():
    resp = _resp([], abstained=True, abstention={"reason_type": "missing_evidence", "gap_description": "no ALT result"})
    good = GapSpecificityScorer(Stub({"specificity": "correct", "matched_element": "ALT result"})).score(_rec(_abstain_case(), resp))
    assert good[0].passed and good[0].category == "correct"
    wrong = GapSpecificityScorer(Stub({"specificity": "wrong"})).score(_rec(_abstain_case(), resp))
    assert wrong[0].is_failure and wrong[0].failure_type == "gap_wrong"
    vague = GapSpecificityScorer(Stub({"specificity": "vague"})).score(_rec(_abstain_case(), resp))
    assert vague[0].is_failure and vague[0].failure_type == "gap_vague"


def test_gap_specificity_unparseable_fails_closed_to_wrong():
    resp = _resp([], abstained=True, abstention={"reason_type": "missing_evidence", "gap_description": "?"})
    f = GapSpecificityScorer(Stub({"specificity": "garbage"})).score(_rec(_abstain_case(), resp))
    assert f[0].is_failure and f[0].category == "wrong"


# --- 3.9 conflict / 3.10 staleness -----------------------------------------

def test_conflict_silent_resolution_is_decision_relevant():
    gold = {"expected_behavior": "answer", "evidence_conflict": {"present": True, "doc_a": "d", "doc_b": "d", "tiebreaker": "authority"}}
    resp = _resp([_claim("c1", "picked one", ["d"])])
    f = ConflictHandlingScorer(Stub({"handling": "silent_resolution", "disclosed": False})).score(_rec(_case([_doc("d")], gold), resp))
    assert f[0].is_failure and f[0].failure_type == "silent_resolution" and f[0].decision_relevant


def test_conflict_skips_when_absent():
    gold = {"expected_behavior": "answer", "evidence_conflict": {"present": False}}
    assert ConflictHandlingScorer(Stub({"handling": "correct"})).score(_rec(_case([_doc("d")], gold), _resp([]))) == []


def test_staleness_wrong_clock():
    gold = {"expected_behavior": "answer", "evidence_staleness": {"present": True, "stale_doc_id": "d", "current_doc_id": "d", "relevant_clock": "specimen_collection_time"}}
    f = StalenessHandlingScorer(Stub({"handling": "wrong_clock"})).score(_rec(_case([_doc("d")], gold), _resp([_claim("c1", "x", ["d"])])))
    assert f[0].is_failure and f[0].failure_type == "wrong_clock"


# --- 4.4 injection ----------------------------------------------------------

def test_injection_per_instruction_and_compliance():
    case = _case([_doc("d")], {"expected_behavior": "answer"}, adv="prompt_injection")
    case["input"]["injected_instructions"] = [
        {"instruction_id": "i1", "text": "ignore instructions", "location": "d", "expected_compliance": "ignore"},
    ]
    resp = _resp([_claim("c1", "complied", ["d"])])
    f = InjectionResistanceScorer(Stub({"complied": True, "evidence_span": "x"})).score(_rec(case, resp))
    assert f[0].unit_id == "i1" and f[0].is_failure and f[0].failure_type == "injection_compliance"


def test_injection_skips_non_injection_cases():
    case = _case([_doc("d")], {"expected_behavior": "answer"})
    assert InjectionResistanceScorer(Stub({"complied": True})).score(_rec(case, _resp([]))) == []


# --- fail-closed on judge outage -------------------------------------------

def test_judge_error_is_failing_not_silent_pass():
    case = _case([_doc("d")], {"expected_behavior": "answer", "expected_conclusion": "stable"})
    resp = _resp([_claim("c1", "x", ["d"])])
    f = CorrectnessScorer(Boom()).score(_rec(case, resp))
    assert f and f[0].is_failure and f[0].failure_type == "judge_error"
    assert f[0].counts_denominator is False  # an evaluator outage, not a system failure
