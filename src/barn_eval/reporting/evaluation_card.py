"""One-page evaluation card (deliverable 9).

Scope, models, datasets, metrics, results, limitations, release recommendation.
Carries the response_source declaration: whether the evaluated responses came
from the RAG prototype or from a simulated fixture. Gate Two makes conflating
the two expensive.
"""

from __future__ import annotations

from .machine import case_rows, rate_rows

_GATE_MARK = {"pass": "PASS", "fail": "FAIL", "not_evaluable": "n/e", "not_evaluated": "pending"}


def render_card(result: dict) -> str:
    """A self-contained markdown evaluation card built from result.json."""
    meta = result.get("run_metadata", {})
    g = result["gates"]
    src = result["response_source"]
    is_fixture = src != "rag_prototype"

    out: list[str] = []
    out += [
        "# BARN-AIS-EVAL-001 — Evaluation Card",
        "",
        f"**Release recommendation: {result['recommendation']}**",
        "",
        "## Scope",
        "Governed evaluation of a clinical RAG system's responses against the "
        "BARN-AIS-EVAL-001 safety framework (Part One metrics, §3.14 release gates).",
        "",
        "## Provenance",
        f"- run_id: `{meta.get('run_id')}`  ·  evaluation_version: `{meta.get('evaluation_version')}`",
        f"- response_source: **{src}** ({result.get('response_source_version')})"
        + ("  — ⚠️ SIMULATED FIXTURE, not a live RAG prototype; these numbers do not "
           "characterise a real system (Gate Two)." if is_fixture else ""),
        f"- judge: {result.get('judge_status')}",
        f"- seed: {meta.get('seed')}  ·  timestamp: {meta.get('timestamp')}",
    ]

    # Judge health
    jh = result.get("judge_health", {})
    if jh.get("judge_error_count"):
        out += ["", f"> **Judge health:** {jh['judge_error_count']} judge call(s) FAILED on "
                    f"{len(jh.get('affected_cases', []))} case(s). Those judge-side metrics are "
                    f"**unmeasured**, not passed."]

    # Datasets
    integ = result["integrity"]
    out += [
        "",
        "## Datasets",
        f"- cases evaluated: **{result['n_cases']}**  ·  joined: {integ['joined']}  ·  "
        f"missing_response: {len(integ['missing_response'])}",
    ]
    if integ["missing_response"]:
        out.append(f"  - missing: {', '.join(integ['missing_response'])}")

    # Gates table
    out += ["", "## Release gates (§3.14)", "", "| Gate | Condition | Status | Detail |", "|---|---|---|---|"]
    for gate in g["gates"]:
        mark = _GATE_MARK.get(gate["status"], gate["status"])
        out.append(f"| {gate['gate']} | {gate['name']} | **{mark}** | {gate['detail']} |")
    if g.get("critical_trigger_counts"):
        out += ["", f"**Critical triggers (§3.12):** {g['critical_trigger_counts']}"]

    # Critical findings
    crit = [c for c in result.get("critical_failures", [])]
    if crit:
        out += ["", "## Critical findings"]
        for c in crit:
            out.append(f"- `{c['case_id']}` — {c['failure_type']} "
                       f"(trigger: {c.get('critical_trigger')}, decision-relevant: {c.get('decision_relevant')})")

    # Metrics
    rrows = [r for r in rate_rows(result) if r["denominator"] and r["metric"] != "4.6"]
    if rrows:
        out += ["", "## Metrics (pooled / per-case failure rate)", "",
                "| Metric | Pooled | Per-case | n/d |", "|---|---|---|---|"]
        for r in rrows:
            out.append(f"| {r['metric']} | {r['pooled']:.3f} | {r['per_case']:.3f} | {r['numerator']}/{r['denominator']} |")

    # Case roster
    out += ["", "## Cases", "", "| Case | Type | Status | Worst | Failures |", "|---|---|---|---|---|"]
    for r in case_rows(result):
        out.append(f"| {r['case_id']} | {r['case_type']} | {r['status']} | {r['worst_severity']} | "
                   f"{r['failure_types'] or '—'} |")

    # Limitations
    out += ["", "## Limitations & assumptions"]
    if is_fixture:
        out.append("- **Responses are a simulated fixture.** Every metric characterises the fixture, "
                   "not a deployed RAG system. Swap `response_source` to `rag_prototype` for a real verdict.")
    if "skipped" in str(result.get("judge_status", "")):
        out.append("- Judge scorers were skipped (no live judge); all judge-dependent metrics "
                   "(groundedness, correctness, prohibited, gap-specificity, conflict/staleness, injection) are unevaluated.")
    if g.get("provisional"):
        out.append("- **Provisional:** at least one gate could not be decided this run "
                   "(reliability §3.14.5 and/or adversarial degradation §3.14.4). Not a release clearance.")
    out.append("- Judge cache is off the call path; live-judge runs are not bit-reproducible.")

    return "\n".join(out) + "\n"
