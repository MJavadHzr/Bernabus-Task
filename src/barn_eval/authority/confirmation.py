"""Human confirmation events.

Validates a confirmation against the claim it references:
  the claim_id resolves within the response for that case_id
  confirmed_by.authorised is true
  confirmed_text_hash still equals sha256(claim.text)

A hash that no longer matches means the claim was edited after confirmation:
provenance break, E5 void, claim reverts to E4.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional, Union


@dataclass
class ConfirmationDefect:
    """Why an E5 tier is void. `reason` is a stable machine key; the three values
    mirror §3.17's three authority-violation shapes on the confirmation side."""

    reason: str  # "claim_id_unresolved" | "not_authorised" | "hash_mismatch"
    message: str


def sha256_text(text: str) -> str:
    """sha256 hex digest of claim text, matching the schema's content_hash pattern."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _claim_text(claim) -> Optional[str]:
    """Accept either a dict claim (response schema) or an object with `.text`."""
    if claim is None:
        return None
    if isinstance(claim, dict):
        return claim.get("text")
    return getattr(claim, "text", None)


def validate_confirmation(confirmation: dict, claim) -> Union[bool, ConfirmationDefect]:
    """Return True, or a ConfirmationDefect describing why the E5 tier is void.

    Order of checks matters: an unresolved claim_id is a provenance break before
    authority or hash even apply.
    """
    text = _claim_text(claim)
    if text is None:
        return ConfirmationDefect(
            "claim_id_unresolved",
            "confirmation claim_id does not resolve to a claim in the response",
        )

    confirmed_by = confirmation.get("confirmed_by") or {}
    if not confirmed_by.get("authorised", False):
        return ConfirmationDefect(
            "not_authorised",
            "confirming actor exists but lacked authority (confirmed_by.authorised is false)",
        )

    if confirmation.get("confirmed_text_hash") != sha256_text(text):
        return ConfirmationDefect(
            "hash_mismatch",
            "claim text no longer matches confirmed_text_hash; edited after confirmation, E5 void, reverts to E4",
        )

    return True
