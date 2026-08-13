"""Orchestration: load -> validate -> join -> score -> aggregate -> gate -> report.

Owns the run identity. Records model version, prompt version, evaluation
version, preprocessor version, seed, response_source, date and run_id before any
scorer executes, so that a run is attributable even if it later fails.

A fixed seed does not make the LLM judge reproducible on its own; reproducibility
for judge-dependent metrics comes from the judge cache (src/judge/cache.py).
"""


def run(config):
    """Execute one evaluation run. Returns the run directory path."""
    raise NotImplementedError
