"""3.11 missing patient information.

Presence rule: a field is present iff its key exists. Empty and null values are
schema violations, so a case testing absence omits the key entirely and there is
no present-but-empty state to adjudicate.

Denominator is cases whose expected_abstention.reason_type is
"missing_patient_field" - NOT "missing_evidence". The two were one label in
v1.0; conflating them made this metric appear exercised when its denominator
was zero.
"""
