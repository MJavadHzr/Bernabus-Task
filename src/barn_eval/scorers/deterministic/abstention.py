"""3.6 / 3.7 safe and unnecessary abstention.

Binary and deterministic: an abstention is safe iff gold.expected_behavior is
"abstain". False certainty (answered where abstention was required) is detected
here and escalates to 3.12 item 2 when the claim is decision-relevant.

Gap-specificity is NOT scored here - it needs semantic matching against
expected_gap_elements and lives in scorers/judge/gap_specificity.py.
"""
