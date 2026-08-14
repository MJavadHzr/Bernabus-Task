"""Machine-readable output: case-level and aggregate, JSON and CSV.

Every loaded case appears in case-level output, including status
"missing_response". Nothing is dropped from any denominator, and the run exits
non-zero when the missing count is above zero (the runner owns the exit code).

These functions consume the canonical `result.json` dict the runner writes, so
`make report` regenerates every table from a committed run without re-scoring.
"""

from __future__ import annotations

import csv
import io

from ..scorers.base import SEVERITY_ORDER


def worst_severity(failures: list[dict]) -> str:
    """Highest-severity label among a case's failures ("none" if clean)."""
    worst = "none"
    for f in failures:
        sev = f.get("severity", "none")
        if SEVERITY_ORDER.index(sev) > SEVERITY_ORDER.index(worst):
            worst = sev
    return worst


def case_rows(result: dict) -> list[dict]:
    """One row per loaded case, joined to its derived failures. Missing-response
    cases appear with status 'missing_response' and no failures - never omitted."""
    failures_by_case = {c["case_id"]: c["failures"] for c in result.get("per_case_failures", [])}
    judge_err_cases = set(result.get("judge_health", {}).get("affected_cases", []))
    rows = []
    for case in result.get("cases", []):
        cid = case["case_id"]
        failures = failures_by_case.get(cid, [])
        rows.append({
            "case_id": cid,
            "case_type": case.get("case_type"),
            "adversarial_category": case.get("adversarial_category") or "",
            "status": case.get("status"),
            "worst_severity": worst_severity(failures),
            "n_failures": len(failures),
            "critical": any(f.get("severity") == "critical" for f in failures),
            "failure_types": ";".join(sorted({f["failure_type"] for f in failures if f.get("failure_type")})),
            "judge_error": cid in judge_err_cases,
        })
    return rows


def rate_rows(result: dict) -> list[dict]:
    """One row per metric section: pooled + per-case rate and its denominator."""
    rows = []
    for section, mr in sorted(result.get("rates", {}).items()):
        rows.append({
            "metric": section,
            "pooled": round(mr.get("pooled", 0.0), 4),
            "per_case": round(mr.get("per_case", 0.0), 4),
            "numerator": mr.get("numerator", 0),
            "denominator": mr.get("denominator", 0),
            "failure_types": ";".join(f"{k}:{v}" for k, v in sorted(mr.get("by_failure_type", {}).items())),
        })
    return rows


def _to_csv(rows: list[dict], fieldnames: list[str]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow(r)
    return buf.getvalue()


def cases_csv(result: dict) -> str:
    rows = case_rows(result)
    return _to_csv(rows, ["case_id", "case_type", "adversarial_category", "status",
                          "worst_severity", "n_failures", "critical", "failure_types", "judge_error"])


def rates_csv(result: dict) -> str:
    rows = rate_rows(result)
    return _to_csv(rows, ["metric", "pooled", "per_case", "numerator", "denominator", "failure_types"])
