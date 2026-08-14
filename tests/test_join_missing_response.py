"""Join semantics: a case with no response becomes status="missing_response",
stays in the denominator, and drives a non-zero exit code.

Guards the failure this harness must not have: a case silently vanishing and
improving every rate by leaving the denominator.
"""

from __future__ import annotations

from barn_eval.harness.join import join
from barn_eval.harness.models import STATUS_MISSING, STATUS_OK


def _case(cid):
    return {
        "schema_version": "1.1",
        "case_id": cid,
        "case_type": "clean",
        "input": {"user_question": "q", "retrieved_documents": []},
        "gold": {"expected_behavior": "answer"},
    }


def _response(cid, abstained=False):
    return {
        "schema_version": "1.1",
        "case_id": cid,
        "answer_text": "a",
        "abstained": abstained,
        "abstention": None,
        "claims": [],
    }


def test_missing_response_stays_in_denominator():
    cases = [_case("clean_001"), _case("clean_002")]
    responses = [_response("clean_001")]  # clean_002 has no response

    records, report = join(cases, responses)

    # one record per case -> nothing dropped
    assert len(records) == len(cases)
    by_id = {r.case_id: r for r in records}
    assert by_id["clean_001"].status == STATUS_OK
    assert by_id["clean_002"].status == STATUS_MISSING
    assert by_id["clean_002"].is_missing

    assert report.missing_response == ["clean_002"]
    assert report.has_missing  # this is what drives the non-zero exit code
    assert report.total_cases == 2
    assert report.joined == 1


def test_orphan_response_is_excluded_and_reported():
    cases = [_case("clean_001")]
    responses = [_response("clean_001"), _response("ghost_999")]

    records, report = join(cases, responses)

    assert [r.case_id for r in records] == ["clean_001"]
    assert report.orphan_responses == ["ghost_999"]
    assert report.has_integrity_error


def test_duplicate_response_is_reported_not_silently_overwritten():
    cases = [_case("clean_001")]
    responses = [_response("clean_001"), _response("clean_001", abstained=True)]

    records, report = join(cases, responses)

    assert report.duplicate_responses == ["clean_001"]
    assert report.has_integrity_error
    # first response wins; the duplicate did not silently replace it
    assert records[0].answered is True


def test_confirmations_grouped_by_case():
    cases = [_case("clean_001")]
    responses = [_response("clean_001")]
    confirmations = [
        {"case_id": "clean_001", "claim_id": "r1c1"},
        {"case_id": "clean_001", "claim_id": "r1c2"},
    ]
    records, _ = join(cases, responses, confirmations)
    assert len(records[0].confirmations) == 2
