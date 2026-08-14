"""Detectors fire on the known planted failures in tests/fixtures/planted_failures.jsonl.

This is why _planted_failure was moved out of the response records: as an
eval-side fixture the known failures become the harness's own oracle, so a
scorer that silently stops working fails a test instead of producing a
clean-looking pass. No scorer may read this file.

  clean_003  prohibited_claim_violation + citation_overreach  (critical)
  clean_008  false_certainty + prohibited_claim_violation     (critical)
  clean_010  fabricated_citation + false_certainty + prohibited (critical)

This file covers the DETERMINISTIC detectors (fabricated_citation, false_certainty).
The judge-side detectors (prohibited_claim_violation, citation_overreach) are
exercised in Phase 4's judge-scorer tests.
"""

from __future__ import annotations

import json
from pathlib import Path

from barn_eval.harness.join import join
from barn_eval.harness.loaders import load_cases, load_responses
from barn_eval.scorers.deterministic.abstention import AbstentionScorer
from barn_eval.scorers.deterministic.citations import CitationScorer

ROOT = Path(__file__).resolve().parents[1]


def _records():
    cases, cerr = load_cases(ROOT / "evaluation_cases/clean.jsonl")
    resps, rerr = load_responses(ROOT / "results/responses/simulated_v1.jsonl")
    assert not cerr and not rerr
    records, _ = join(cases, resps)
    return {r.case_id: r for r in records}


def _failure_types(record):
    findings = CitationScorer().score(record) + AbstentionScorer().score(record)
    return {f.failure_type for f in findings if f.is_failure}


def test_planted_fixture_is_not_read_by_scorers():
    # The oracle exists and is eval-side only; scorers never open it.
    planted = ROOT / "tests/fixtures/planted_failures.jsonl"
    assert planted.exists()
    ids = {json.loads(line)["case_id"] for line in planted.read_text().splitlines() if line.strip()}
    assert ids == {"clean_003", "clean_008", "clean_010"}


def test_clean_010_fabricated_and_false_certainty_fire():
    rec = _records()["clean_010"]
    types = _failure_types(rec)
    assert "fabricated_citation" in types  # r10c1 cites doc_c010b, not in the retrieved set
    assert "false_certainty" in types      # expected abstain, answered instead


def test_clean_008_false_certainty_fires():
    rec = _records()["clean_008"]
    assert "false_certainty" in _failure_types(rec)


def test_correct_abstentions_do_not_trip_false_certainty():
    recs = _records()
    for cid in ("clean_009", "clean_011"):
        assert "false_certainty" not in _failure_types(recs[cid])
        # and they register as safe abstentions
        safe = [f for f in AbstentionScorer().score(recs[cid]) if f.category == "safe"]
        assert safe and safe[0].passed


def test_clean_baseline_answer_has_no_deterministic_failures():
    rec = _records()["clean_001"]
    assert _failure_types(rec) == set()
