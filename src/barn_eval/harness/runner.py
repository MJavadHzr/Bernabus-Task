"""Orchestration: load -> validate -> join -> score -> aggregate -> gate -> report.

Owns the run identity. Records model version, prompt version, evaluation version,
preprocessor version, seed, response_source, date and run_id before any scorer
executes, so that a run is attributable even if it later fails.

A fixed seed does not make the LLM judge reproducible on its own; reproducibility
for judge-dependent metrics comes from the judge cache (src/barn_eval/judge/cache.py),
which is deliberately off the call path in this build - so a live-judge run is
labelled non-reproducible rather than pretending otherwise.

The reliability step (Phase 6, block condition 3.14.5) is a declared slot here:
until it runs it contributes no verdict-flip rate, gate 5 stays NOT_EVALUATED, and
the recommendation is at best PROVISIONAL_PASS - never a clean clearance.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..aggregation import aggregate, load_severity_map, load_thresholds
from ..judge.client import JudgeConfigError, build_judge
from ..reporting import write_reports
from ..scorers.deterministic import DETERMINISTIC_SCORERS
from ..scorers.judge import build_judge_scorers
from .config import load_config, resolve, resolve_globs
from .join import join
from .loaders import load_cases, load_confirmations, load_responses
from .models import RunMetadata
from .registry_checks import check_registry

# Exit codes: operational failures are non-zero; a completed run with a BLOCK
# recommendation is a SUCCESSFUL evaluation (exit 0) - the verdict is the payload,
# not an error. Registry/schema breakage is fail-closed non-zero.
EXIT_OK = 0
EXIT_MISSING = 1        # cases with no response (config-gated)
EXIT_PRECONDITION = 2   # registry violations / schema errors: the suite itself is broken


@dataclass
class ValidateResult:
    n_cases: int
    schema_errors: list
    registry_violations: list

    @property
    def ok(self) -> bool:
        return not self.schema_errors and not self.registry_violations


@dataclass
class RunResult:
    run_dir: Path
    exit_code: int
    recommendation: str
    aggregate: object = None
    judge_status: str = ""
    join_report: object = None
    validate: Optional[ValidateResult] = None


# -- helpers ----------------------------------------------------------------
def _git_sha(base: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(base), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:  # pragma: no cover - git absent
        return ""


def _load_all_cases(config) -> tuple[list, list]:
    cases, errors = [], []
    for path in resolve_globs(config, config["data"]["cases"]):
        c, e = load_cases(path)
        cases.extend(c)
        errors.extend(e)
    return cases, errors


def _load_patients(config) -> dict:
    return json.loads(resolve(config, config["data"]["patients"]).read_text(encoding="utf-8"))


def _run_metadata(config) -> RunMetadata:
    run_cfg = config["run"]
    jcfg = config.get("judge", {})
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    sha = _git_sha(Path(config["_base_dir"]))
    return RunMetadata(
        run_id=f"{ts}_{sha}" if sha else ts,
        seed=run_cfg["seed"],
        evaluation_version=run_cfg["evaluation_version"],
        timestamp=ts,
        response_source=config["response_source"],
        response_source_version=config.get("response_source_version"),
        preprocessor_version=run_cfg.get("preprocessor_version"),
        prompt_version=jcfg.get("prompt_version"),
        judge_model=jcfg.get("model") if jcfg.get("enabled") else None,
        experiment_id=run_cfg.get("experiment_id"),
    )


def _build_scorers(config) -> tuple[list, str]:
    """Deterministic scorers always; judge scorers only if a live judge can be
    built. replay_only / disabled / missing key => judge metrics are SKIPPED and
    recorded, not silently dropped."""
    scorers = [cls() for cls in DETERMINISTIC_SCORERS]
    jcfg = config.get("judge", {})
    if not jcfg.get("enabled"):
        return scorers, "disabled"
    try:
        judge = build_judge(jcfg)
    except JudgeConfigError as exc:
        return scorers, f"skipped ({exc})"
    scorers += build_judge_scorers(judge)
    return scorers, f"enabled ({jcfg.get('model')})"


# -- validate ---------------------------------------------------------------
def validate(config) -> ValidateResult:
    """Schema + registry preconditions only; no scoring."""
    cases, schema_errors = _load_all_cases(config)
    violations = check_registry(cases, _load_patients(config))
    return ValidateResult(n_cases=len(cases), schema_errors=schema_errors, registry_violations=violations)


def rehash_cases(config) -> int:
    """Recompute every retrieved_document.content_hash = sha256(content), in place.

    A maintenance utility (make hash-cases): after editing case content the hash
    must be regenerated or the integrity check (PartFour.5) will correctly reject
    the drift. Returns the number of documents rehashed.
    """
    changed = 0
    for path in resolve_globs(config, config["data"]["cases"]):
        lines_out = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                lines_out.append(line)
                continue
            case = json.loads(line)
            for doc in case.get("input", {}).get("retrieved_documents", []):
                h = hashlib.sha256((doc.get("content") or "").encode("utf-8")).hexdigest()
                if doc.get("content_hash") != h:
                    doc["content_hash"] = h
                    changed += 1
            lines_out.append(json.dumps(case, ensure_ascii=False))
        path.write_text("\n".join(lines_out) + "\n", encoding="utf-8")
    return changed


# -- run --------------------------------------------------------------------
def run(config, *, evaluator_flip_rate: Optional[float] = None) -> RunResult:
    """Execute one evaluation run. Writes results/runs/<run_id>/ and returns a
    RunResult (run dir, exit code, recommendation, aggregate)."""
    meta = _run_metadata(config)
    run_dir = resolve(config, config["run"]["output_dir"]) / meta.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # 1. load + precondition
    cases, schema_errors = _load_all_cases(config)
    patients = _load_patients(config)
    violations = check_registry(cases, patients)
    vresult = ValidateResult(n_cases=len(cases), schema_errors=schema_errors, registry_violations=violations)

    # 2. responses + confirmations
    responses, rerr = load_responses(resolve(config, config["data"]["responses"]))
    confirmations, cferr = load_confirmations(resolve(config, config["data"]["confirmations"]))
    schema_errors = schema_errors + rerr + cferr

    # Fail-closed: a broken suite (registry violations) is not scored - scoring a
    # suite that failed its own preconditions would report meaningless numbers.
    if violations:
        _write_precondition_failure(run_dir, meta, vresult, config)
        return RunResult(run_dir=run_dir, exit_code=EXIT_PRECONDITION, recommendation="ABORTED",
                         judge_status="not run", validate=vresult)

    # 3. join
    records, join_report = join(cases, responses, confirmations)

    # 4. score
    scorers, judge_status = _build_scorers(config)
    findings = [f for s in scorers for r in records for f in s.score(r)]

    # 5. aggregate (reliability slot: evaluator_flip_rate stays None until Phase 6)
    paths = config.get("paths", {})
    sev = load_severity_map(resolve(config, paths.get("severity_map", "configs/severity_map.yaml")))
    thr = load_thresholds(resolve(config, paths.get("thresholds", "configs/thresholds.yaml")))
    agg = aggregate(findings, records, severity_map=sev, thresholds=thr, evaluator_flip_rate=evaluator_flip_rate)

    # 6. write outputs
    _write_run(run_dir, meta, config, records, findings, agg, join_report, schema_errors, judge_status)

    # 7. exit code: missing responses are operational failures when configured so.
    exit_code = EXIT_OK
    if join_report.has_missing and config.get("failure_handling", {}).get("exit_nonzero_on_missing", True):
        exit_code = EXIT_MISSING
    if schema_errors:
        exit_code = EXIT_PRECONDITION

    return RunResult(run_dir=run_dir, exit_code=exit_code, recommendation=agg.recommendation,
                     aggregate=agg, judge_status=judge_status, join_report=join_report, validate=vresult)


# -- serialization ----------------------------------------------------------
def _finding_dict(f) -> dict:
    d = asdict(f)
    d["is_failure"] = f.is_failure
    return d


def _rate_dict(mr) -> dict:
    d = asdict(mr)
    d["pooled"] = mr.pooled
    return d


def _gates_dict(report) -> dict:
    return {
        "recommendation": report.recommendation,
        "blocked": report.blocked,
        "provisional": report.provisional,
        "critical_trigger_counts": report.critical_trigger_counts,
        "gates": [asdict(g) | {"blocking": g.blocking} for g in report.results],
    }


def _judge_health(findings) -> dict:
    """Judge outage accounting. A judge_error is NOT a system failure and is kept
    out of severities/denominators - but if it is also kept out of the report, a
    run where the judge failed on every call looks identical to a clean judge run.
    So the count is surfaced explicitly: a run with judge_errors has UNMEASURED
    judge-side metrics and must not be read as if the judge passed them."""
    errors = [f for f in findings if f.failure_type == "judge_error"]
    by_section = Counter(f.section for f in errors)
    return {"judge_error_count": len(errors), "by_section": dict(by_section),
            "affected_cases": sorted({f.case_id for f in errors})}


def _result_dict(meta, config, records, agg, findings, join_report, schema_errors, judge_status) -> dict:
    by_case: dict[str, dict] = {}
    for v in agg.severities:
        entry = by_case.setdefault(v.case_id, {"case_id": v.case_id, "failures": []})
        entry["failures"].append({"section": v.section, "failure_type": v.failure_type,
                                  "severity": v.severity, "decision_relevant": v.decision_relevant,
                                  "critical_trigger": v.critical_trigger, "unit_id": v.unit_id})
    return {
        "run_metadata": meta.model_dump(),
        "response_source": config["response_source"],
        "response_source_version": config.get("response_source_version"),
        "judge_status": judge_status,
        "judge_health": _judge_health(findings),
        "recommendation": agg.recommendation,
        "n_cases": agg.n_cases,
        # Full roster: every loaded case appears, including missing_response, so
        # case-level reports never silently omit a case (Part Two requirement 10).
        "cases": [
            {"case_id": r.case_id, "case_type": r.case_type,
             "adversarial_category": r.adversarial_category,
             "status": "missing_response" if r.is_missing else "ok"}
            for r in records
        ],
        "gates": _gates_dict(agg.gates),
        "rates": {k: _rate_dict(v) for k, v in agg.rates.items()},
        "critical_failures": [asdict(v) | {"is_critical": v.is_critical} for v in agg.critical_failures],
        "per_case_failures": list(by_case.values()),
        "integrity": {
            "total_cases": join_report.total_cases,
            "joined": join_report.joined,
            "missing_response": join_report.missing_response,
            "orphan_responses": join_report.orphan_responses,
            "duplicate_responses": join_report.duplicate_responses,
        },
        "schema_errors": [asdict(e) for e in schema_errors],
    }


def _write_run(run_dir, meta, config, records, findings, agg, join_report, schema_errors, judge_status) -> None:
    (run_dir / "run_metadata.json").write_text(json.dumps(meta.model_dump(), indent=2), encoding="utf-8")
    with (run_dir / "findings.jsonl").open("w", encoding="utf-8") as fh:
        for f in findings:
            fh.write(json.dumps(_finding_dict(f), ensure_ascii=False) + "\n")
    result = _result_dict(meta, config, records, agg, findings, join_report, schema_errors, judge_status)
    (run_dir / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    # Human summary, evaluation card and CSV tables (Phase 7) render from result.json.
    write_reports(result, run_dir)


def _write_precondition_failure(run_dir, meta, vresult, config) -> None:
    payload = {
        "run_metadata": meta.model_dump(),
        "recommendation": "ABORTED",
        "reason": "registry precondition violations; suite not scored (fail-closed)",
        "registry_violations": [asdict(v) for v in vresult.registry_violations],
        "schema_errors": [asdict(e) for e in vresult.schema_errors],
    }
    (run_dir / "result.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    (run_dir / "run_metadata.json").write_text(json.dumps(meta.model_dump(), indent=2), encoding="utf-8")


def run_from_path(config_path, **kw) -> RunResult:
    return run(load_config(config_path), **kw)
