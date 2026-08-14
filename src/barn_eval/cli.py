"""Command-line entry point. Gate One: one documented command, clean machine, no help needed.

  validate     schema + registry preconditions, no scoring
  run          full evaluation, writes results/runs/<run_id>/
  reliability  evaluator invariance suite
  report       regenerate summary and evaluation card from an existing run
"""

from __future__ import annotations

import argparse
import json
import sys

from .harness.config import load_config, resolve
from .harness.runner import (
    EXIT_OK,
    EXIT_PRECONDITION,
    rehash_cases,
    run,
    validate,
)
from .reporting import render_summary

DEFAULT_CONFIG = "configs/run.default.yaml"


def _cmd_validate(args) -> int:
    config = load_config(args.config)
    if args.rehash:
        n = rehash_cases(config)
        print(f"rehashed {n} document content_hash value(s)")
    v = validate(config)
    print(f"loaded {v.n_cases} case(s)")
    for e in v.schema_errors:
        print(f"  SCHEMA  {e.file}:{e.line} {e.case_id or ''} {e.message}")
    for viol in v.registry_violations:
        print(f"  REGISTRY {viol.case_id} [{viol.check}] {viol.message}")
    if v.ok:
        print("OK: schema + registry preconditions pass")
        return EXIT_OK
    print(f"FAILED: {len(v.schema_errors)} schema error(s), {len(v.registry_violations)} registry violation(s)")
    return EXIT_PRECONDITION


def _cmd_run(args) -> int:
    config = load_config(args.config)
    result = run(config)
    print(render_summary(json.loads((result.run_dir / "result.json").read_text())))
    print(f"run dir: {result.run_dir}")
    print(f"judge: {result.judge_status}")
    return result.exit_code


def _cmd_reliability(args) -> int:
    # Phase 6 slot. Until implemented, gate 5 stays NOT_EVALUATED (see runner /
    # aggregation.gates); this command declares that state rather than faking a pass.
    print("reliability (block condition §3.14.5) is not yet implemented in this build.")
    print("gate 5 remains NOT_EVALUATED and every run is at best PROVISIONAL_PASS.")
    print("the evaluator-invariance suite needs a live judge, which is currently unavailable.")
    return EXIT_OK


def _cmd_report(args) -> int:
    config = load_config(args.config)
    runs_dir = resolve(config, config["run"]["output_dir"])
    if args.run_id:
        run_dir = runs_dir / args.run_id
    else:
        candidates = sorted((p for p in runs_dir.glob("*") if (p / "result.json").exists()))
        if not candidates:
            print(f"no runs found under {runs_dir}", file=sys.stderr)
            return EXIT_PRECONDITION
        run_dir = candidates[-1]
    result_path = run_dir / "result.json"
    if not result_path.exists():
        print(f"no result.json in {run_dir}", file=sys.stderr)
        return EXIT_PRECONDITION
    print(render_summary(json.loads(result_path.read_text())))
    print(f"run dir: {run_dir}")
    return EXIT_OK


def main(argv=None) -> int:
    """Dispatch subcommands. Returns a process exit code."""
    parser = argparse.ArgumentParser(prog="barn_eval", description="BARN-AIS-EVAL-001 harness")
    sub = parser.add_subparsers(dest="command", required=True)

    p_val = sub.add_parser("validate", help="schema + registry preconditions, no scoring")
    p_val.add_argument("--config", default=DEFAULT_CONFIG)
    p_val.add_argument("--rehash", action="store_true", help="recompute case content_hash values in place")
    p_val.set_defaults(func=_cmd_validate)

    p_run = sub.add_parser("run", help="full evaluation run")
    p_run.add_argument("--config", default=DEFAULT_CONFIG)
    p_run.set_defaults(func=_cmd_run)

    p_rel = sub.add_parser("reliability", help="evaluator invariance suite (§3.14.5)")
    p_rel.add_argument("--config", default=DEFAULT_CONFIG)
    p_rel.set_defaults(func=_cmd_reliability)

    p_rep = sub.add_parser("report", help="summary + card from an existing run")
    p_rep.add_argument("--config", default=DEFAULT_CONFIG)
    p_rep.add_argument("--run-id", default=None, help="run id to report (default: latest)")
    p_rep.set_defaults(func=_cmd_report)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
