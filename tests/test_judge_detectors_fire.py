"""Judge-side detectors fire on the planted failures (companion to
test_detectors_fire.py, which covers the deterministic half).

  clean_003  citation_overreach (r3c2) + prohibited_claim_violation (recurrence)
  clean_008  prohibited_claim_violation (methotrexate dose)
  clean_010  prohibited_claim_violation (DEXA exists / no repeat needed)

The judge is a SCRIPTED FAKE, not the live model: these tests assert the scorer
PLUMBING (given a judge verdict, the right Finding is emitted), never the LLM's
judgment. No network is touched. The fake's rules are transparent substring
checks that are unambiguously correct for these specific planted inputs.
"""

from __future__ import annotations

from pathlib import Path

from barn_eval.harness.join import join
from barn_eval.harness.loaders import load_cases, load_responses
from barn_eval.judge.client import JudgeVerdict
from barn_eval.scorers.judge.groundedness import GroundednessScorer
from barn_eval.scorers.judge.prohibited import ProhibitedClaimScorer

ROOT = Path(__file__).resolve().parents[1]


class ScriptedJudge:
    """A transparent stand-in for the live judge, driven only by the payload."""

    model = "scripted-fake"

    def __call__(self, prompt_name, payload):
        if prompt_name == "prohibited":
            data = self._prohibited(payload)
        elif prompt_name == "groundedness":
            data = self._groundedness(payload)
        else:  # pragma: no cover - not used by these tests
            data = {}
        return JudgeVerdict(data=data, model=self.model, prompt_name=prompt_name, prompt_version="v1")

    @staticmethod
    def _prohibited(payload):
        ans = payload["answer_text"].lower()
        prohibited = payload["prohibited_claim"].lower()
        violated = (
            ("recurrence" in prohibited and "recurrence" in ans)
            or ("methotrexate" in prohibited and "methotrexate" in ans)
            or ("dexa" in prohibited and "dexa" in ans)
            or ("bone density" in prohibited and "no repeat" in ans)
        )
        return {"violated": violated, "violating_span": None, "rationale": "scripted"}

    @staticmethod
    def _groundedness(payload):
        claim = payload["claim_text"].lower()
        # A prognostic leap off a measurement-only source is overreach.
        if "recurrence" in claim and "unlikely" in claim:
            return {
                "category": "citation_failure",
                "citation_failure_subtype": "overreach",
                "unsupported_span": "recurrence is unlikely",
                "rationale": "scripted overreach",
            }
        return {"category": "grounded", "citation_failure_subtype": None, "unsupported_span": None, "rationale": "scripted"}


def _records():
    cases, cerr = load_cases(ROOT / "evaluation_cases/clean.jsonl")
    resps, rerr = load_responses(ROOT / "results/responses/simulated_v1.jsonl")
    assert not cerr and not rerr
    records, _ = join(cases, resps)
    return {r.case_id: r for r in records}


def test_clean_003_citation_overreach_fires():
    rec = _records()["clean_003"]
    findings = GroundednessScorer(ScriptedJudge()).score(rec)
    types = {f.failure_type for f in findings if f.is_failure}
    assert "citation_overreach" in types
    over = [f for f in findings if f.failure_type == "citation_overreach"]
    assert over[0].unit_id == "r3c2" and over[0].category == "citation_failure"


def test_clean_003_prohibited_recurrence_fires_critical():
    rec = _records()["clean_003"]
    findings = ProhibitedClaimScorer(ScriptedJudge()).score(rec)
    viol = [f for f in findings if f.failure_type == "prohibited_claim_violation"]
    assert viol and viol[0].severity == "critical" and viol[0].decision_relevant


def test_clean_008_prohibited_methotrexate_fires():
    rec = _records()["clean_008"]
    findings = ProhibitedClaimScorer(ScriptedJudge()).score(rec)
    assert any(f.failure_type == "prohibited_claim_violation" and f.severity == "critical" for f in findings)


def test_clean_010_prohibited_dexa_fires_both():
    rec = _records()["clean_010"]
    findings = ProhibitedClaimScorer(ScriptedJudge()).score(rec)
    viol = [f for f in findings if f.failure_type == "prohibited_claim_violation"]
    # Both prohibited claims (DEXA exists / no repeat needed) are asserted.
    assert len(viol) == 2
    severities = {f.severity for f in viol}
    assert severities == {"critical", "major"}


def test_clean_baseline_grounded_claim_has_no_judge_failure():
    rec = _records()["clean_001"]
    findings = GroundednessScorer(ScriptedJudge()).score(rec)
    assert all(f.passed for f in findings)


def test_groundability_audit_set_is_wellformed_and_covers_all_categories():
    import json

    path = ROOT / "evaluation_cases/groundability_audit.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    assert rows, "groundability audit set must not be empty (it is the judge's ground truth)"

    required = {"audit_id", "user_question", "claim_text", "cited_documents", "gold_category"}
    ids = set()
    for r in rows:
        assert required <= r.keys(), f"missing keys in {r.get('audit_id')}"
        assert r["gold_category"] in {"grounded", "unsupported", "citation_failure"}
        if r["gold_category"] == "citation_failure":
            assert r.get("gold_subtype") in {"wrong_source", "overreach"}
        ids.add(r["audit_id"])
    assert len(ids) == len(rows), "audit_id must be unique"

    # The reference set must exercise every partition the judge can return, or it
    # cannot detect a judge that collapses two categories together.
    categories = {r["gold_category"] for r in rows}
    subtypes = {r.get("gold_subtype") for r in rows if r["gold_category"] == "citation_failure"}
    assert categories == {"grounded", "unsupported", "citation_failure"}
    assert subtypes == {"wrong_source", "overreach"}
