"""4.6 latency and estimated inference cost.

Broken out by case type (clean vs adversarial, answered vs abstained), since
abstention and safety-check paths may have different profiles.

Both fields are self-reported by the system under test. Where the harness does
not measure wall-clock time itself these figures are attested, not observed, and
are labelled as such in the report.
"""
