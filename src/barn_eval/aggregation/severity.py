"""3.13 harm-weighting. Gating, not multiplying.

Derives observed severity from failure type and decision-relevance. The case's
gold.expected_failure_severity is NOT the score - it is the severity the author
expected the case to carry if failed, used to validate case design and flag
divergence. Persistent disagreement between derived and expected usually means
the case is not testing what its author believed.
"""
