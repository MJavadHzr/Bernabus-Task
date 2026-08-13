"""Join semantics: a case with no response becomes status="missing_response",
stays in the denominator, and drives a non-zero exit code.

Guards the failure this harness must not have: a case silently vanishing and
improving every rate by leaving the denominator.
"""
