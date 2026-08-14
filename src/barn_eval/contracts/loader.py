"""Schema access.

Loads the three JSON Schema contracts and exposes validators. Every record
entering the harness is validated here; no module parses a raw dict without
having passed through this gate first.

Contracts:
  evaluation_case.schema.json    gold side, authored by the eval team
  model_response.schema.json     observed side, the RAG system's output contract
  human_confirmation.schema.json confirmation events, third author, third file
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft7Validator

_CONTRACTS_DIR = Path(__file__).resolve().parent

# name stem -> schema filename
_SCHEMAS = {
    "evaluation_case": "evaluation_case.schema.json",
    "model_response": "model_response.schema.json",
    "human_confirmation": "human_confirmation.schema.json",
}


@lru_cache(maxsize=None)
def load_schema(name: str) -> dict:
    """Return a parsed schema by filename stem. Raises if unknown."""
    if name not in _SCHEMAS:
        raise KeyError(f"unknown schema {name!r}; known: {sorted(_SCHEMAS)}")
    path = _CONTRACTS_DIR / _SCHEMAS[name]
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=None)
def validator_for(name: str) -> Draft7Validator:
    """Return a Draft7Validator for the named schema."""
    schema = load_schema(name)
    Draft7Validator.check_schema(schema)
    return Draft7Validator(schema)
