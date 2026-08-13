"""Schema access.

Loads the three JSON Schema contracts and exposes validators. Every record
entering the harness is validated here; no module parses a raw dict without
having passed through this gate first.

Contracts:
  evaluation_case.schema.json    gold side, authored by the eval team
  model_response.schema.json     observed side, the RAG system's output contract
  human_confirmation.schema.json confirmation events, third author, third file
"""


def load_schema(name: str) -> dict:
    """Return a parsed schema by filename stem. Raises if unknown."""
    raise NotImplementedError


def validator_for(name: str):
    """Return a Draft7Validator for the named schema."""
    raise NotImplementedError
