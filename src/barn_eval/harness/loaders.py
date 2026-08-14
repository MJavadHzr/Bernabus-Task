"""JSONL loading with schema validation.

Every loader validates against src/barn_eval/contracts before returning. A record that
fails validation is reported with its case_id and line number and counted as a
load failure; it is never silently skipped (Part Two requirement 10).

Loaders return (records, errors). Callers must inspect `errors`; an empty list
means every line validated. Nothing is dropped without a corresponding LoadError.
"""

from __future__ import annotations

import glob
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..contracts.loader import validator_for


@dataclass
class LoadError:
    """A single line that could not be loaded, kept so nothing vanishes silently."""

    file: str
    line: int
    case_id: Optional[str]
    message: str


def _load_jsonl(path: str | os.PathLike, schema_name: str) -> tuple[list[dict], list[LoadError]]:
    validator = validator_for(schema_name)
    records: list[dict] = []
    errors: list[LoadError] = []
    p = Path(path)
    with p.open(encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError as exc:
                errors.append(LoadError(str(p), lineno, None, f"JSON parse error: {exc}"))
                continue
            schema_errors = sorted(validator.iter_errors(obj), key=lambda e: list(e.path))
            if schema_errors:
                case_id = obj.get("case_id") if isinstance(obj, dict) else None
                msg = "; ".join(e.message for e in schema_errors)
                errors.append(LoadError(str(p), lineno, case_id, msg))
                continue
            records.append(obj)
    return records, errors


def load_cases(path: str | os.PathLike) -> tuple[list[dict], list[LoadError]]:
    """Load and validate evaluation cases from one JSONL file."""
    return _load_jsonl(path, "evaluation_case")


def load_responses(path: str | os.PathLike) -> tuple[list[dict], list[LoadError]]:
    """Load and validate model responses from one JSONL file."""
    return _load_jsonl(path, "model_response")


def load_confirmations(path: str | os.PathLike) -> tuple[list[dict], list[LoadError]]:
    """Load and validate human confirmation events.

    Accepts a single JSONL file or a directory of ``*.jsonl`` confirmation files
    (results/confirmations/). A missing path yields no records and no errors:
    confirmations are optional and their absence is not a load failure.
    """
    p = Path(path)
    if p.is_dir():
        records: list[dict] = []
        errors: list[LoadError] = []
        for f in sorted(glob.glob(str(p / "*.jsonl"))):
            recs, errs = _load_jsonl(f, "human_confirmation")
            records.extend(recs)
            errors.extend(errs)
        return records, errors
    if not p.exists():
        return [], []
    return _load_jsonl(p, "human_confirmation")
