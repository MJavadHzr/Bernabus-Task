"""Replayable judge cache. A REPRODUCIBILITY REQUIREMENT, not an optimisation.

A fixed random seed does not make an LLM judge deterministic. Without a
content-addressed, replayable cache, a reviewer running on a clean machine gets
different numbers for every judge-dependent metric - which fails Gate One.

Key: sha256 of (judge model, prompt version, prompt name, canonicalised payload).
Committed with the run so the run can be replayed offline.
"""


def cache_key(model: str, prompt_version: str, prompt_name: str, payload: dict) -> str:
    """Content-addressed key. Payload canonicalised before hashing."""
    raise NotImplementedError
