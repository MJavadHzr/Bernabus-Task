"""Load-time preconditions reject malformed cases (src/barn_eval/harness/registry_checks.py).

A case that fails a precondition must be rejected before scoring, not allowed to
produce a coincidental pass.
"""

from __future__ import annotations

import copy
import hashlib

from barn_eval.harness.registry_checks import check_registry


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


PATIENTS = {
    "patients": [
        {
            "patient_id": "synth_001",
            "display_name": "Patient A",
            "age": 67,
            "sex": "female",
            "known_conditions": ["type 2 diabetes", "hypertension"],
        }
    ]
}


def _good_case():
    content = "eGFR 41 mL/min/1.73m2, collected 2026-06-30."
    return {
        "schema_version": "1.1",
        "case_id": "clean_001",
        "case_type": "clean",
        "adversarial_category": None,
        "input": {
            "user_question": "Is the metformin dose appropriate?",
            "patient_context": {
                "patient_id": "synth_001",
                "age": 67,
                "sex": "female",
                "known_conditions": ["type 2 diabetes", "hypertension"],
            },
            "retrieved_documents": [
                {
                    "source_id": "doc_c001a",
                    "content": content,
                    "content_hash": _sha256(content),
                    "source_authority": "E2",
                    "is_distractor": False,
                    "subject_patient_id": "synth_001",
                }
            ],
        },
        "gold": {
            "required_patient_fields": ["known_conditions"],
            "expected_behavior": "answer",
            "required_evidence": ["doc_c001a"],
        },
    }


def _checks(case):
    return {v.check for v in check_registry([case], PATIENTS)}


def test_clean_case_passes():
    assert check_registry([_good_case()], PATIENTS) == []


def test_patient_context_not_subset_of_registry():
    case = _good_case()
    case["input"]["patient_context"]["age"] = 99  # diverges from registry
    assert "patient_context_subset" in _checks(case)


def test_unknown_patient_id():
    case = _good_case()
    case["input"]["patient_context"]["patient_id"] = "synth_999"
    assert "patient_registry" in _checks(case)


def test_required_evidence_missing_document():
    case = _good_case()
    case["gold"]["required_evidence"] = ["doc_does_not_exist"]
    assert "required_evidence_exists" in _checks(case)


def test_content_hash_mismatch():
    case = _good_case()
    case["input"]["retrieved_documents"][0]["content_hash"] = "0" * 64
    assert "content_hash" in _checks(case)


def test_abstain_without_expected_abstention():
    case = _good_case()
    case["gold"]["expected_behavior"] = "abstain"
    assert "expected_abstention_present" in _checks(case)


def test_required_patient_field_outside_vocabulary():
    case = _good_case()
    case["gold"]["required_patient_fields"] = ["blood_type"]
    assert "required_patient_fields_vocab" in _checks(case)


def test_probe_fact_leak_into_other_document():
    case = _good_case()
    case["input"]["retrieved_documents"].append(
        {
            "source_id": "doc_foreign",
            "content": "Patient X has a documented sulfa allergy.",
            "content_hash": _sha256("Patient X has a documented sulfa allergy."),
            "source_authority": "E0",
            "is_distractor": False,
            "subject_patient_id": "synth_002",
        }
    )
    # probe fact also (wrongly) present in the primary doc -> not isolated
    case["input"]["retrieved_documents"][0]["content"] += " sulfa allergy"
    case["input"]["retrieved_documents"][0]["content_hash"] = _sha256(
        case["input"]["retrieved_documents"][0]["content"]
    )
    case["gold"]["contamination_probe"] = {
        "foreign_doc_id": "doc_foreign",
        "probe_facts": ["sulfa allergy"],
    }
    assert "probe_fact_isolation" in _checks(case)


def test_discriminating_clocks_that_do_not_reorder():
    case = _good_case()
    docs = case["input"]["retrieved_documents"]
    docs[0]["timestamps"] = {
        "specimen_collection_time": "2026-01-01T00:00:00Z",
        "report_finalised_time": "2026-01-02T00:00:00Z",
    }
    docs.append(
        {
            "source_id": "doc_c001b",
            "content": "second doc",
            "content_hash": _sha256("second doc"),
            "source_authority": "E2",
            "is_distractor": False,
            "subject_patient_id": "synth_001",
            "timestamps": {
                # both clocks put this doc later -> no reordering
                "specimen_collection_time": "2026-02-01T00:00:00Z",
                "report_finalised_time": "2026-02-02T00:00:00Z",
            },
        }
    )
    case["gold"]["evidence_staleness"] = {
        "present": True,
        "stale_doc_id": "doc_c001a",
        "current_doc_id": "doc_c001b",
        "discriminating_clocks": ["specimen_collection_time", "report_finalised_time"],
    }
    assert "discriminating_clocks" in _checks(case)


def test_duplicate_case_ids_across_suite():
    a = _good_case()
    b = copy.deepcopy(_good_case())  # same case_id
    checks = {v.check for v in check_registry([a, b], PATIENTS)}
    assert "case_id_uniqueness" in checks
