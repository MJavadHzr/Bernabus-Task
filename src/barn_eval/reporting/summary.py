"""Human-readable run summary.

Leads with gate status, not with average scores. A summary whose headline is a
high aggregate invites exactly the reading 3.12 exists to prevent.

Separates: verified findings, declared assumptions, and metrics with a zero
denominator. A metric with no denominator is never presented as a metric that
passed.
"""

from __future__ import annotations

from .machine import case_rows

# Metric sections that are measurements, not pass/fail rates - excluded from the
# "metrics" table so a 0/0 latency line is never read as a passed safety metric.
_MEASUREMENT_SECTIONS = {"latency-cost"}


def _judge_health_line(result: dict) -> list[str]:
    jh = result.get("judge_health", {})
    n = jh.get("judge_error_count", 0)
    if not n:
        return []
    return [
        f"\nWARNING: {n} judge call(s) FAILED on {len(jh.get('affected_cases', []))} case(s) "
        f"{jh.get('by_section', {})} — those judge-side metrics are UNMEASURED, not passed.\n"
    ]


def render_summary(result: dict) -> str:
    """Gate-led plain-text/markdown summary for the terminal and summary.md."""
    g = result["gates"]
    integ = result["integrity"]
    lines = [
        "="*15,
        f"RECOMMENDATION: {result['recommendation']}",
        f"\t- response_source:\t{result['response_source']} ({result.get('response_source_version')})",
        f"\t- judge:\t\t{result.get('judge_status')}",
        f"\t- cases:\t\t{result['n_cases']}",
        f"\t- missing_response:\t{len(integ['missing_response'])}",
    ]
    lines += _judge_health_line(result)

    lines += ["", "RELEASE GATES:"]
    for gate in g["gates"]:
        lines.append(f"  [{gate['status']:<13}] gate {gate['gate']} {gate['name']}: {gate['detail']}")
    if g.get("critical_trigger_counts"):
        lines += ["", f"critical triggers: {g['critical_trigger_counts']}"]

    # Verified findings: cases carrying a failure, worst-severity first.
    rows = [r for r in case_rows(result) if r["n_failures"] or r["status"] != "ok"]
    if rows:
        lines += ["", "VERIFIED FINDINGS (per case):"]
        for r in sorted(rows, key=lambda x: (not x["critical"], x["case_id"])):
            flag = "CRITICAL " if r["critical"] else ""
            detail = r["failure_types"] or r["status"]
            lines.append(f"  {r['case_id']:<12} {flag}[{r['worst_severity']}] {detail}")

    # Metrics: real rates only; zero-denominator metrics listed separately.
    measured, empty = [], []
    for section, mr in sorted(result.get("rates", {}).items()):
        if section in _MEASUREMENT_SECTIONS:
            continue
        (measured if mr.get("denominator") else empty).append((section, mr))
    if measured:
        lines += ["", "METRICS (pooled / per-case failure rate):"]
        for section, mr in measured:
            lines.append(f"  {section:<10} {mr['pooled']:.3f} / {mr['per_case']:.3f}   "
                         f"({mr['numerator']}/{mr['denominator']})")
    if empty:
        lines += ["", "ZERO-DENOMINATOR METRICS (not evaluated — not a pass):",
                  "  " + ", ".join(s for s, _ in empty)]

    # Declared assumptions (Gate Two: fixture vs system must never be conflated).
    lines += ["", "DECLARED ASSUMPTIONS:",
              f"  - responses are from '{result['response_source']}', not a live RAG prototype"
              if result["response_source"] != "rag_prototype"
              else "  - responses are from the RAG prototype under test"]
    if "skipped" in str(result.get("judge_status", "")):
        lines.append("  - judge scorers were SKIPPED; judge-side metrics are unevaluated this run")
    if g.get("provisional") and not g.get("blocked"):
        lines.append("  - PROVISIONAL: a gate could not be decided (reliability and/or adversarial "
                     "degradation unmeasured) — not a release clearance")
    return "\n".join(lines) + "\n"
