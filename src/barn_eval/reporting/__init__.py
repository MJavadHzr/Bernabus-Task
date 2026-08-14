"""Reporting: human summary, one-page evaluation card, machine tables.

All renderers consume the canonical `result.json` the runner writes, so
`make report` regenerates every artefact from a committed run without re-scoring.
`write_reports` is the single call the runner/CLI use to emit the artefact set.
"""

from __future__ import annotations

from pathlib import Path

from .evaluation_card import render_card
from .machine import case_rows, cases_csv, rate_rows, rates_csv
from .summary import render_summary

__all__ = [
    "render_summary",
    "render_card",
    "cases_csv",
    "rates_csv",
    "case_rows",
    "rate_rows",
    "write_reports",
]


def write_reports(result: dict, run_dir: str | Path) -> dict[str, Path]:
    """Write summary.md, evaluation_card.md, cases.csv, rates.csv into run_dir.

    Returns {name: path}. result.json itself is written by the runner (it is the
    canonical machine output these views render from)."""
    run_dir = Path(run_dir)
    artefacts = {
        "summary.md": render_summary(result),
        "evaluation_card.md": render_card(result),
        "cases.csv": cases_csv(result),
        "rates.csv": rates_csv(result),
    }
    written: dict[str, Path] = {}
    for name, content in artefacts.items():
        path = run_dir / name
        path.write_text(content, encoding="utf-8")
        written[name] = path
    return written
