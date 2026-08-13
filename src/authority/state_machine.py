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


def promote(claim, event=None):
    """Return the claim at its new tier, or raise AuthorityViolation."""
    raise NotImplementedError


class AuthorityViolation(Exception):
    """Raised on any attempt to promote without a valid confirmation event."""
