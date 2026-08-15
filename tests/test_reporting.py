"""Phase 7 — reporting renders from result.json: summary, card, CSV tables.

The renderers are pure functions of the result dict, so these build synthetic
result dicts to pin the behaviours that matter: every case appears (incl.
missing_response), zero-denominator metrics are not shown as passes, the fixture
declaration is loud, and a judge outage is surfaced rather than hidden.
"""

from __future__ import annotations

from barn_eval.reporting import cases_csv, rates_csv, render_card, render_summary, write_reports
from barn_eval.reporting.machine import case_rows, worst_severity


def _result(**over):
    base = {
        "run_metadata": {"run_id": "R1", "evaluation_version": "1.1.0", "seed": 1, "timestamp": "T"},
        "response_source": "simulated_fixture",
        "response_source_version": "v1",
        "judge_status": "skipped (replay_only)",
        "judge_health": {"judge_error_count": 0, "by_section": {}, "affected_cases": []},
        "recommendation": "BLOCK",
        "n_cases": 3,
        "cases": [
            {"case_id": "c1", "case_type": "clean", "adversarial_category": None, "status": "ok"},
            {"case_id": "c2", "case_type": "clean", "adversarial_category": None, "status": "ok"},
            {"case_id": "c3", "case_type": "clean", "adversarial_category": None, "status": "missing_response"},
        ],
        "gates": {
            "recommendation": "BLOCK", "blocked": True, "provisional": True,
            "critical_trigger_counts": {"false_certainty": 1},
            "gates": [
                {"gate": 1, "name": "critical_safety_failure", "status": "fail", "detail": "1/3"},
                {"gate": 5, "name": "evaluator_instability", "status": "not_evaluated", "detail": "pending"},
            ],
        },
        "rates": {
            "critical-safety": {"pooled": 1.0, "per_case": 1.0, "numerator": 1, "denominator": 1, "by_failure_type": {"false_certainty": 1}},
            "contamination": {"pooled": 0.0, "per_case": 0.0, "numerator": 0, "denominator": 0, "by_failure_type": {}},
            "latency-cost": {"pooled": 0.0, "per_case": 0.0, "numerator": 0, "denominator": 6, "by_failure_type": {}},
        },
        "critical_failures": [
            {"case_id": "c1", "failure_type": "false_certainty", "critical_trigger": "false_certainty",
             "decision_relevant": True, "is_critical": True},
        ],
        "per_case_failures": [
            {"case_id": "c1", "failures": [
                {"section": "critical-safety", "failure_type": "false_certainty", "severity": "critical",
                 "decision_relevant": True, "critical_trigger": "false_certainty", "unit_id": None}]},
        ],
        "integrity": {"total_cases": 3, "joined": 2, "missing_response": ["c3"],
                      "orphan_responses": [], "duplicate_responses": []},
        "schema_errors": [],
    }
    base.update(over)
    return base


# --- machine ----------------------------------------------------------------

def test_worst_severity_orders_correctly():
    assert worst_severity([{"severity": "minor"}, {"severity": "critical"}, {"severity": "major"}]) == "critical"
    assert worst_severity([]) == "none"


def test_case_rows_include_every_case_including_missing():
    rows = case_rows(_result())
    ids = {r["case_id"]: r for r in rows}
    assert set(ids) == {"c1", "c2", "c3"}
    assert ids["c3"]["status"] == "missing_response"       # never omitted
    assert ids["c1"]["critical"] and ids["c1"]["worst_severity"] == "critical"
    assert ids["c2"]["worst_severity"] == "none"


def test_cases_csv_has_header_and_all_rows():
    csv = cases_csv(_result())
    assert csv.splitlines()[0].startswith("case_id,case_type")
    assert len([ln for ln in csv.splitlines() if ln]) == 4     # header + 3 cases


def test_rates_csv_includes_measurement_sections():
    assert "latency-cost" in rates_csv(_result())


# --- summary ----------------------------------------------------------------

def test_summary_is_gate_led_and_lists_findings():
    s = render_summary(_result())
    assert "RECOMMENDATION: BLOCK" in s
    assert "GATES" in s and "critical_safety_failure" in s
    assert "c1" in s and "false_certainty" in s


def test_summary_separates_zero_denominator_metrics():
    s = render_summary(_result())
    assert "ZERO-DENOMINATOR METRICS" in s and "contamination" in s.split("ZERO-DENOMINATOR")[1]
    # a measurement section (4.6) is not shown as a passed safety metric
    assert "latency-cost" not in s.split("METRICS")[1].split("ZERO-DENOMINATOR")[0]


def test_summary_declares_fixture_and_skipped_judge():
    s = render_summary(_result())
    assert "simulated_fixture" in s and "not a live RAG prototype" in s
    assert "judge scorers were SKIPPED" in s


def test_summary_surfaces_judge_errors():
    s = render_summary(_result(judge_health={"judge_error_count": 4, "by_section": {"grounded": 4}, "affected_cases": ["c1", "c2"]}))
    assert "WARNING" in s and "UNMEASURED" in s


# --- evaluation card --------------------------------------------------------

def test_card_headlines_recommendation_and_flags_fixture():
    card = render_card(_result())
    assert "Release recommendation: BLOCK" in card
    assert "SIMULATED FIXTURE" in card and "Gate Two" in card
    assert "| 1 | critical_safety_failure | **FAIL**" in card
    assert "`c1` — false_certainty" in card


def test_card_case_table_lists_missing_response():
    card = render_card(_result())
    assert "| c3 | clean | missing_response" in card


# --- write_reports ----------------------------------------------------------

def test_write_reports_emits_all_artifacts(tmp_path):
    written = write_reports(_result(), tmp_path)
    assert set(written) == {"summary.md", "evaluation_card.md", "cases.csv", "rates.csv"}
    for p in written.values():
        assert p.exists() and p.read_text().strip()
