"""Canonical in-memory records.

EvaluationRecord is the single object every scorer consumes: one case joined to
its response (and any confirmation events), plus harness-computed fields that
appear in neither input file.

Harness-computed, never authored (input contract 3):
  supporting_text_span   per claim x citation, enables overreach detection
  status                 "ok" | "missing_response"
  run metadata           evaluation_version, run_id, seed, timestamp

status exists so that a case with no response still produces a record. Nothing
is dropped from any denominator.
"""


class EvaluationRecord:
    """One case joined to one response. Scorers read this and nothing else."""


class RunMetadata:
    """Run-level provenance: model, prompt, evaluation and preprocessor versions,
    seed, response_source, timestamp, run_id."""
