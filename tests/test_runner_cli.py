"""Phase 8 — orchestration + CLI over the real clean suite.

Exercises the full load -> join -> score -> aggregate -> gate -> write path end to
end (deterministic scorers; the judge is skipped under the default replay_only
config, exactly as a live run without a key behaves), plus the CLI dispatch and
the rehash utility.
"""

from __future__ import annotations

import json

import yaml

from barn_eval import cli
from barn_eval.harness.config import load_config, resolve, resolve_globs
from barn_eval.harness.runner import EXIT_OK, rehash_cases, run, validate

REAL_CONFIG = "configs/run.default.yaml"


# --- config loading ---------------------------------------------------------

def test_load_config_sets_base_dir_and_resolves():
    cfg = load_config(REAL_CONFIG)
    assert cfg["_base_dir"] and cfg["run"]["evaluation_version"] == "1.1.0"
    cases = resolve_globs(cfg, cfg["data"]["cases"])
    assert cases and all(p.is_absolute() for p in cases)
    assert resolve(cfg, "/tmp/x").as_posix() == "/tmp/x"  # absolute passes through


# --- validate ---------------------------------------------------------------

def test_validate_clean_suite_passes():
    v = validate(load_config(REAL_CONFIG))
    assert v.ok and v.n_cases == 11 and not v.schema_errors and not v.registry_violations


# --- run --------------------------------------------------------------------

def _config_with_output(tmp_path):
    cfg = load_config(REAL_CONFIG)
    cfg["run"]["output_dir"] = str(tmp_path / "runs")
    return cfg


def test_run_writes_outputs_and_blocks(tmp_path):
    result = run(_config_with_output(tmp_path))
    assert result.exit_code == EXIT_OK          # BLOCK is a successful evaluation
    assert result.recommendation == "BLOCK"
    for name in ("result.json", "findings.jsonl", "run_metadata.json",
                 "summary.md", "evaluation_card.md", "cases.csv", "rates.csv"):
        assert (result.run_dir / name).exists()


def test_run_result_json_is_wellformed(tmp_path):
    result = run(_config_with_output(tmp_path))
    data = json.loads((result.run_dir / "result.json").read_text())
    assert data["recommendation"] == "BLOCK"
    assert data["response_source"] == "simulated_fixture"
    assert "skipped" in data["judge_status"]           # replay_only => judge skipped, recorded
    assert data["integrity"]["missing_response"] == []
    # gate 1 fired on the two false_certainty cases; gates 4/5 undecided => provisional-eligible
    g1 = next(g for g in data["gates"]["gates"] if g["gate"] == 1)
    assert g1["status"] == "fail"
    assert data["gates"]["critical_trigger_counts"] == {"false_certainty": 2}
    cases_with_failures = {c["case_id"] for c in data["per_case_failures"]}
    assert {"clean_008", "clean_010"} <= cases_with_failures


def test_run_metadata_records_provenance(tmp_path):
    result = run(_config_with_output(tmp_path))
    meta = json.loads((result.run_dir / "run_metadata.json").read_text())
    assert meta["response_source"] == "simulated_fixture"
    assert meta["evaluation_version"] == "1.1.0"
    assert meta["run_id"]  # timestamp (+ git sha)


# --- rehash utility ---------------------------------------------------------

def test_rehash_fixes_wrong_hash_then_is_idempotent(tmp_path):
    case = {
        "case_id": "x1",
        "input": {"retrieved_documents": [
            {"source_id": "d1", "content": "hello", "content_hash": "WRONG"},
        ]},
    }
    f = tmp_path / "cases.jsonl"
    f.write_text(json.dumps(case) + "\n")
    cfg = {"_base_dir": str(tmp_path), "data": {"cases": ["cases.jsonl"]}}

    assert rehash_cases(cfg) == 1                      # one wrong hash corrected
    fixed = json.loads(f.read_text().splitlines()[0])
    import hashlib
    assert fixed["input"]["retrieved_documents"][0]["content_hash"] == hashlib.sha256(b"hello").hexdigest()
    assert rehash_cases(cfg) == 0                      # nothing left to change


# --- CLI dispatch -----------------------------------------------------------

def _abs_config_file(tmp_path):
    """A self-contained config with every path absolute, so `main` can run it from
    anywhere and write into tmp."""
    cfg = load_config(REAL_CONFIG)
    cfg["data"]["patients"] = str(resolve(cfg, cfg["data"]["patients"]))
    cfg["data"]["cases"] = [str(p) for p in resolve_globs(cfg, cfg["data"]["cases"])]
    cfg["data"]["responses"] = str(resolve(cfg, cfg["data"]["responses"]))
    cfg["data"]["confirmations"] = str(resolve(cfg, cfg["data"]["confirmations"]))
    cfg["paths"] = {
        "severity_map": str(resolve(cfg, "configs/severity_map.yaml")),
        "thresholds": str(resolve(cfg, "configs/thresholds.yaml")),
    }
    cfg["run"]["output_dir"] = str(tmp_path / "runs")
    for k in ("_base_dir", "_config_path"):
        cfg.pop(k, None)
    path = tmp_path / "cfg.yaml"
    path.write_text(yaml.safe_dump(cfg))
    return str(path)


def test_cli_validate_and_reliability_return_zero(capsys):
    assert cli.main(["validate", "--config", REAL_CONFIG]) == 0
    assert cli.main(["reliability", "--config", REAL_CONFIG]) == 0
    out = capsys.readouterr().out
    assert "NOT_EVALUATED" in out  # reliability declares its pending state


def test_cli_run_then_report_roundtrip(tmp_path, capsys):
    cfg_file = _abs_config_file(tmp_path)
    assert cli.main(["run", "--config", cfg_file]) == 0
    assert "RECOMMENDATION: BLOCK" in capsys.readouterr().out
    assert cli.main(["report", "--config", cfg_file]) == 0
    assert "RECOMMENDATION: BLOCK" in capsys.readouterr().out
