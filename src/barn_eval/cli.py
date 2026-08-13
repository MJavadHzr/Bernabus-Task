"""Command-line entry point. Gate One: one documented command, clean machine, no help needed.

  validate     schema + registry preconditions, no scoring
  run          full evaluation, writes results/runs/<run_id>/
  reliability  evaluator invariance suite
  report       regenerate summary and evaluation card from an existing run
"""


def main(argv=None):
    """Dispatch subcommands. Returns a process exit code."""
    raise NotImplementedError


if __name__ == "__main__":
    raise SystemExit(main())
