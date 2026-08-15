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
    read_flip_rate,
    rehash_cases,
    run,
    run_reliability,
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
    flip = read_flip_rate(args.reliability) if args.reliability else None
    result = run(config, evaluator_flip_rate=flip)
    print(render_summary(json.loads((result.run_dir / "result.json").read_text())))
    print(f"run dir: {result.run_dir}")
    print(f"judge: {result.judge_status}")
    if args.reliability:
        print(f"reliability: verdict_flip_rate={flip} (from {args.reliability})")
    return result.exit_code


def _cmd_reliability(args) -> int:
    """Evaluate the evaluator (§3.14.5): verdict-flip rate under meaning-preserving
    perturbation, plus judge-vs-reference disagreement. Feeds gate 5."""
    config = load_config(args.config)
    res = run_reliability(config, seed=args.seed)
    if res.verdict_flip_rate is None:
        print(f"reliability SKIPPED: {res.judge_status}")
        print("gate 5 stays NOT_EVALUATED; a run consuming this is at best PROVISIONAL_PASS.")
        return EXIT_OK

    rep = res.report
    print(f"judge: {res.judge_status}")
    print(f"EVALUATOR INVARIANCE (§3.14.5): verdict_flip_rate={rep.verdict_flip_rate:.3f}  "
          f"({rep.n_flips}/{rep.n_compared} unit-verdicts flipped) -> gate 5 {res.gate5_status.upper()}")
    for p in rep.per_perturbation:
        print(f"  {p.name:<16} flips {p.flip_count}/{p.compared}  (rate {p.flip_rate:.3f}"
              f"{'; judge_errors=' + str(p.judge_errors) if p.judge_errors else ''})")
    if rep.judge_errors_excluded:
        print(f"  NOTE: {rep.judge_errors_excluded} unit-verdict(s) excluded as judge outages, not flips")
    if res.disagreement is not None:
        d = res.disagreement
        print(f"JUDGE vs REFERENCE ({d.metric}): disagreement_rate={d.disagreement_rate:.3f} "
              f"({d.disagreements}/{d.n}); judge_errors={d.judge_errors}")
    if res.out_path:
        print(f"wrote {res.out_path}")
        print(f"feed it into a scored run:  barn_eval run --reliability {res.out_path}")
    return res.exit_code


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
    p_run.add_argument("--reliability", default=None,
                       help="reliability.json to source gate 5's verdict_flip_rate from")
    p_run.set_defaults(func=_cmd_run)

    p_rel = sub.add_parser("reliability", help="evaluator invariance suite (§3.14.5)")
    p_rel.add_argument("--config", default=DEFAULT_CONFIG)
    p_rel.add_argument("--seed", type=int, default=None,
                       help="perturbation seed (default: run.seed from config)")
    p_rel.set_defaults(func=_cmd_reliability)

    p_rep = sub.add_parser("report", help="summary + card from an existing run")
    p_rep.add_argument("--config", default=DEFAULT_CONFIG)
    p_rep.add_argument("--run-id", default=None, help="run id to report (default: latest)")
    p_rep.set_defaults(func=_cmd_report)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
