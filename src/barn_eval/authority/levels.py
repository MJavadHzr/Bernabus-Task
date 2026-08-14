"""The E0-E5 evidence authority model (Part Four).

  E0  raw source record                    cannot be produced by a model
  E1  normalised or extracted fact         retains a link to its E0 parent
  E2  validated calculated result          retains inputs and validation
  E3  deterministic rule result            reproducible from the same inputs
  E4  AI-generated draft                   never primary; not promotable by assertion
  E5  authorised human-confirmed           reachable from E4 only via confirmation
"""

from __future__ import annotations

from enum import IntEnum
from typing import Union


class AuthorityLevel(IntEnum):
    """E0-E5, ordered. Model-producible tiers are E4 only.

    IntEnum so the tiers carry a natural order (E0 < ... < E5) for the state
    machine; the integer value is an index, not a clinical authority score.
    """

    E0 = 0
    E1 = 1
    E2 = 2
    E3 = 3
    E4 = 4
    E5 = 5

    @classmethod
    def from_str(cls, value: Union["AuthorityLevel", str, None]) -> "AuthorityLevel":
        """Coerce a tier. None -> E4 (an AI-generated draft is never primary; a
        system that omits asserted_authority degrades to E4 rather than crashing)."""
        if value is None:
            return cls.E4
        if isinstance(value, cls):
            return value
        try:
            return cls[value]  # "E4" -> AuthorityLevel.E4
        except KeyError as exc:
            raise ValueError(f"unknown authority tier {value!r}") from exc

    @property
    def model_producible(self) -> bool:
        """True only for E4 — the single tier a model may legitimately originate."""
        return self is AuthorityLevel.E4

    @property
    def requires_confirmation(self) -> bool:
        """E5 is reachable only via an authorised human confirmation."""
        return self is AuthorityLevel.E5


# Tiers a model CANNOT produce; asserting one on a generated claim is
# promotion-by-assertion (§3.17 type 1).
PRIMARY_TIERS = frozenset(
    {AuthorityLevel.E0, AuthorityLevel.E1, AuthorityLevel.E2, AuthorityLevel.E3}
)
