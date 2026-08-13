"""The E0-E5 evidence authority model (Part Four).

  E0  raw source record                    cannot be produced by a model
  E1  normalised or extracted fact         retains a link to its E0 parent
  E2  validated calculated result          retains inputs and validation
  E3  deterministic rule result            reproducible from the same inputs
  E4  AI-generated draft                   never primary; not promotable by assertion
  E5  authorised human-confirmed           reachable from E4 only via confirmation
"""


class AuthorityLevel:
    """E0-E5, ordered. Model-producible tiers are E4 only."""
