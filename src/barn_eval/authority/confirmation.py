"""Human confirmation events.

Validates a confirmation against the claim it references:
  the claim_id resolves within the response for that case_id
  confirmed_by.authorised is true
  confirmed_text_hash still equals sha256(claim.text)

A hash that no longer matches means the claim was edited after confirmation:
provenance break, E5 void, claim reverts to E4.
"""


def validate_confirmation(confirmation, claim):
    """Return True, or a ConfirmationDefect describing why the E5 tier is void."""
    raise NotImplementedError
