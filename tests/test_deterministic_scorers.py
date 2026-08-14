"""Exact-check scorers, on hand-built minimal records.

Deterministic scorers are the ones the framework leans on hardest, because they
are exempt from the 5 reliability burden. That exemption is only earned if
they are correct.
"""

from __future__ import annotations

import hashlib

from barn_eval.harness.models import EvaluationRecord
from barn_eval.scorers.deterministic.abstention import AbstentionScorer
from barn_eval.scorers.deterministic.authority import AuthorityScorer
from barn_eval.scorers.deterministic.citations import CitationScorer
from barn_eval.scorers.deterministic.contamination import ContaminationScorer
from barn_eval.scorers.deterministic.patient_context import PatientContextScorer
from barn_eval.scorers.deterministic.retrieval import RetrievalScorer


def _sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _doc(source_id, content="c", subject="synth_001", **kw):
    d = {
        "source_id": source_id,
        "content": content,
        "content_hash": _sha256(content),
        "source_authority": "E2",
        "is_distractor": False,
        "subject_patient_id": subject,
        "retrieval_score": 0.9,
        "source_version": "final",
        "source_date": "2026-06-30",
    }
    d.update(kw)
    return d


def _record(case, response, confirmations=None):
    return EvaluationRecord(
        case=case, response=response, confirmations=confirmations or [], status="ok"
    )


def _base_case(docs, gold=None, patient="synth_001"):
    return {
        "case_id": "t1",
        "case_type": "clean",
        "adversarial_category": None,
        "input": {
            "user_question": "q",
            "patient_context": {"patient_id": patient},
            "retrieved_documents": docs,
        },
        "gold": gold or {"expected_behavior": "answer"},
    }


def _resp(claims, abstained=False, abstention=None):
    return {
        "case_id": "t1",
        "answer_text": " ".join(c["text"] for c in claims),
        "abstained": abstained,
        "abstention": abstention,
        "claims": claims,
    }


def _claim(cid, text, citations, authority=None):
    return {"claim_id": cid, "text": text, "citations": citations, "asserted_authority": authority}


# --- 3.5 fabricated citation -----------------------------------------------

def test_fabricated_citation_fires_on_nonexistent_source():
    case = _base_case([_doc("doc_a")])
    resp = _resp([_claim("c1", "x", ["doc_ghost"])])
    findings = CitationScorer().score(_record(case, resp))
    fab = [f for f in findings if f.section == "3.5"]
    assert fab and fab[0].is_failure and fab[0].failure_type == "fabricated_citation"


def test_existing_citation_is_not_fabricated():
    case = _base_case([_doc("doc_a")])
    resp = _resp([_claim("c1", "x", ["doc_a"])])
    findings = CitationScorer().score(_record(case, resp))
    fab = [f for f in findings if f.section == "3.5"]
    assert fab and fab[0].passed


# --- 4.3 citation recall (document-level, incl. abstentions) ---------------

def test_citation_recall_missing_required_evidence():
    case = _base_case([_doc("doc_a")], gold={"expected_behavior": "answer", "required_evidence": ["doc_a"]})
    resp = _resp([_claim("c1", "x", [])])  # cites nothing
    findings = CitationScorer().score(_record(case, resp))
    rec = [f for f in findings if f.section == "4.3"]
    assert rec and rec[0].is_failure and rec[0].failure_type == "missing_required_citation"


# --- 3.16 contamination -----------------------------------------------------

def test_cited_contamination_foreign_patient():
    case = _base_case([_doc("doc_a", subject="synth_002")], patient="synth_001")
    resp = _resp([_claim("c1", "x", ["doc_a"])])
    findings = ContaminationScorer().score(_record(case, resp))
    hits = [f for f in findings if f.is_failure and f.category == "cited"]
    assert hits


def test_uncited_contamination_probe_fact():
    gold = {
        "expected_behavior": "answer",
        "contamination_probe": {"foreign_doc_id": "doc_f", "probe_facts": ["sulfa allergy"]},
    }
    case = _base_case([_doc("doc_a"), _doc("doc_f", subject="synth_002")], gold=gold)
    resp = _resp([_claim("c1", "Patient has a sulfa allergy noted.", ["doc_a"])])
    findings = ContaminationScorer().score(_record(case, resp))
    hits = [f for f in findings if f.is_failure and f.category == "uncited"]
    assert hits


def test_general_reference_null_subject_never_contaminates():
    case = _base_case([_doc("doc_a", subject=None)], patient="synth_001")
    resp = _resp([_claim("c1", "x", ["doc_a"])])
    findings = ContaminationScorer().score(_record(case, resp))
    assert all(f.passed for f in findings)


# --- 3.17 authority violations ---------------------------------------------

def test_promotion_by_assertion():
    case = _base_case([_doc("doc_a")])
    resp = _resp([_claim("c1", "x", ["doc_a"], authority="E1")])
    findings = AuthorityScorer().score(_record(case, resp))
    assert any(f.failure_type == "promotion_by_assertion" for f in findings)


def test_e5_without_confirmation_is_unauthorised():
    case = _base_case([_doc("doc_a")])
    resp = _resp([_claim("c1", "x", ["doc_a"], authority="E5")])
    findings = AuthorityScorer().score(_record(case, resp))
    assert any(f.failure_type == "unauthorised_promotion" for f in findings)


def test_e5_with_valid_confirmation_passes():
    case = _base_case([_doc("doc_a")])
    text = "confirmed claim"
    resp = _resp([_claim("c1", text, ["doc_a"], authority="E5")])
    conf = {
        "case_id": "t1",
        "claim_id": "c1",
        "confirmed_by": {"actor_id": "a", "role": "md", "authorised": True},
        "confirmed_text_hash": _sha256(text),
    }
    findings = AuthorityScorer().score(_record(case, resp, [conf]))
    assert all(f.passed for f in findings)


def test_e5_hash_mismatch_is_broken_provenance():
    case = _base_case([_doc("doc_a")])
    resp = _resp([_claim("c1", "edited text", ["doc_a"], authority="E5")])
    conf = {
        "case_id": "t1",
        "claim_id": "c1",
        "confirmed_by": {"actor_id": "a", "role": "md", "authorised": True},
        "confirmed_text_hash": _sha256("original text"),
    }
    findings = AuthorityScorer().score(_record(case, resp, [conf]))
    assert any(f.failure_type == "broken_provenance" for f in findings)


def test_null_authority_is_e4_and_clean():
    case = _base_case([_doc("doc_a")])
    resp = _resp([_claim("c1", "x", ["doc_a"], authority=None)])
    findings = AuthorityScorer().score(_record(case, resp))
    assert all(f.passed for f in findings)


# --- 3.6/3.7 abstention + false certainty ----------------------------------

def test_safe_abstention():
    gold = {"expected_behavior": "abstain", "expected_abstention": {"reason_type": "missing_evidence", "expected_gap_elements": ["x"]}}
    case = _base_case([_doc("doc_a")], gold=gold)
    resp = _resp([], abstained=True, abstention={"reason_type": "missing_evidence"})
    findings = AbstentionScorer().score(_record(case, resp))
    assert any(f.section == "3.6" and f.category == "safe" and f.passed for f in findings)


def test_unnecessary_abstention():
    case = _base_case([_doc("doc_a")], gold={"expected_behavior": "answer"})
    resp = _resp([], abstained=True, abstention={"reason_type": "missing_evidence"})
    findings = AbstentionScorer().score(_record(case, resp))
    assert any(f.failure_type == "unnecessary_abstention" for f in findings)


def test_false_certainty_when_answered_but_abstain_expected():
    gold = {"expected_behavior": "abstain", "expected_abstention": {"reason_type": "missing_evidence", "expected_gap_elements": ["x"]}}
    case = _base_case([_doc("doc_a")], gold=gold)
    resp = _resp([_claim("c1", "confident answer", ["doc_a"])], abstained=False)
    findings = AbstentionScorer().score(_record(case, resp))
    fc = [f for f in findings if f.failure_type == "false_certainty"]
    assert fc and fc[0].decision_relevant


# --- 3.11 missing patient field --------------------------------------------

def test_missing_patient_field_detected():
    gold = {
        "expected_behavior": "abstain",
        "required_patient_fields": ["allergies"],
        "expected_abstention": {"reason_type": "missing_patient_field", "expected_gap_elements": ["allergy list"]},
    }
    case = _base_case([_doc("doc_a")], gold=gold)  # patient_context omits 'allergies'
    resp = _resp([], abstained=True, abstention={"reason_type": "missing_patient_field", "missing_field": "allergies"})
    findings = PatientContextScorer().score(_record(case, resp))
    assert findings and findings[0].passed


def test_missing_patient_field_undetected_when_answered():
    gold = {
        "expected_behavior": "abstain",
        "required_patient_fields": ["allergies"],
        "expected_abstention": {"reason_type": "missing_patient_field", "expected_gap_elements": ["allergy list"]},
    }
    case = _base_case([_doc("doc_a")], gold=gold)
    resp = _resp([_claim("c1", "amoxicillin is fine", ["doc_a"])], abstained=False)
    findings = PatientContextScorer().score(_record(case, resp))
    assert findings and findings[0].is_failure


def test_missing_evidence_case_not_in_denominator():
    gold = {
        "expected_behavior": "abstain",
        "expected_abstention": {"reason_type": "missing_evidence", "expected_gap_elements": ["x"]},
    }
    case = _base_case([_doc("doc_a")], gold=gold)
    resp = _resp([], abstained=True, abstention={"reason_type": "missing_evidence"})
    assert PatientContextScorer().score(_record(case, resp)) == []


# --- 4.1 retrieval recall ---------------------------------------------------

def test_retrieval_recall_present():
    gold = {"expected_behavior": "answer", "required_evidence": ["doc_a"]}
    case = _base_case([_doc("doc_a")], gold=gold)
    findings = RetrievalScorer().score(_record(case, _resp([])))
    recall = [f for f in findings if f.unit_id == "doc_a"]
    assert recall and recall[0].passed and recall[0].value == 1.0
