"""Enforced promotion logic.

Part Four requirements 1, 2 and 6 are demonstrated here BY CONSTRUCTION and by
the tests in tests/test_authority_state_machine.py - not by measurement. A
response record cannot show that a pipeline's promotion logic is sound; it can
only show whether a violation is visible in the output.

The report must keep construction evidence and measurement evidence apart
(3.17 scope limitation).

  promote(claim, event) raises unless event is a valid, authorised confirmation
  confirmation appends; it never overwrites the original E4 text or its history
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Optional, Union

from .confirmation import validate_confirmation
from .levels import PRIMARY_TIERS, AuthorityLevel


class AuthorityViolation(Exception):
    """Raised on any attempt to promote without a valid confirmation event."""


@dataclass
class Claim:
    """Authority-side view of a generated claim.

    `original_text` and `history` are append-only: a confirmation never rewrites
    the original E4 text or erases prior events (Part Four requirement 6). The E5
    tier is always reconstructible from, and revocable by, the recorded history.
    """

    claim_id: str
    text: str
    level: AuthorityLevel = AuthorityLevel.E4
    original_text: Optional[str] = None
    history: tuple = ()

    def __post_init__(self):
        if self.original_text is None:
            self.original_text = self.text


def assert_producible(asserted: Union[AuthorityLevel, str, None]) -> AuthorityLevel:
    """Validate the tier a model asserts for a generated claim.

    Enforces "E4 cannot be treated as E0/E1/E2/E3": a model may originate only E4.
    Raises AuthorityViolation on any primary tier (promotion-by-assertion, §3.17
    type 1). None -> E4. E5 is allowed to pass here but is only *valid* with a
    matching confirmation (checked by promote()).
    """
    level = AuthorityLevel.from_str(asserted)
    if level in PRIMARY_TIERS:
        raise AuthorityViolation(
            f"model-generated claim asserts {level.name}, a tier a model cannot produce"
        )
    return level


def promote(claim: Claim, event: Optional[dict] = None) -> Claim:
    """Return the claim at its new tier, or raise AuthorityViolation.

    The ONLY promotion the machine permits is E4 -> E5, and only via a valid,
    authorised confirmation event. Appends the confirmation to history without
    touching original_text.
    """
    if claim.level is not AuthorityLevel.E4:
        raise AuthorityViolation(
            f"only E4 claims may be promoted; claim {claim.claim_id!r} is {claim.level.name}"
        )
    if event is None:
        raise AuthorityViolation(
            f"E4 -> E5 requires a confirmation event; none supplied for {claim.claim_id!r}"
        )

    result = validate_confirmation(event, claim)
    if result is not True:
        raise AuthorityViolation(f"invalid confirmation ({result.reason}): {result.message}")

    appended = claim.history + (
        {
            "event": "confirmation",
            "confirmation_id": event.get("confirmation_id"),
            "actor_id": (event.get("confirmed_by") or {}).get("actor_id"),
            "confirmed_text_hash": event.get("confirmed_text_hash"),
        },
    )
    # New object at E5; original_text carried through unchanged.
    return replace(claim, level=AuthorityLevel.E5, history=appended)


def revalidate(claim: Claim, event: dict) -> Claim:
    """Re-check a confirmed claim's provenance against its confirmation.

    If the claim text was edited after confirmation the recorded hash no longer
    matches: the E5 tier is void and the claim reverts to E4. History is retained
    so the break is auditable, never erased.
    """
    result = validate_confirmation(event, claim)
    if result is not True and claim.level is AuthorityLevel.E5:
        return replace(claim, level=AuthorityLevel.E4)
    return claim
