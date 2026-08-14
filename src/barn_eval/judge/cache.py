"""Replayable judge cache. A REPRODUCIBILITY REQUIREMENT, not an optimisation.

A fixed random seed does not make an LLM judge deterministic. Without a
content-addressed, replayable cache, a reviewer running on a clean machine gets
different numbers for every judge-dependent metric - which fails Gate One.

Key: sha256 of (judge model, prompt version, prompt name, canonicalised payload).
Committed with the run so the run can be replayed offline.

STATUS (v1): `cache_key` is implemented and pure so the future seam is ready, but
the store/replay path is intentionally NOT wired into judge/client.py yet - this
build makes live judge calls and is therefore not bit-reproducible. Reinstating
replay means routing Judge.__call__ through a store keyed by this function; no
scorer changes.
"""

from __future__ import annotations

import hashlib
import json


def _canonical(payload: dict) -> str:
    """Stable serialisation: sorted keys, no incidental whitespace.

    Two payloads that differ only in key order or spacing MUST hash the same, or
    the cache would miss on semantically identical calls and silently go live.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def cache_key(model: str, prompt_version: str, prompt_name: str, payload: dict) -> str:
    """Content-addressed key. Payload canonicalised before hashing."""
    material = "\x00".join([model, prompt_version, prompt_name, _canonical(payload)])
    return hashlib.sha256(material.encode("utf-8")).hexdigest()
