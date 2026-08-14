"""3.11 missing patient information.

Presence rule: a field is present iff its key exists. Empty and null values are
schema violations, so a case testing absence omits the key entirely and there is
no present-but-empty state to adjudicate.

Denominator is cases whose expected_abstention.reason_type is
"missing_patient_field" - NOT "missing_evidence". The two were one label in
v1.0; conflating them made this metric appear exercised when its denominator
was zero.
"""

from __future__ import annotations

from ..base import Finding, Scorer


class PatientContextScorer(Scorer):
    """3.11 detection rate: correctly abstained + field named, over missing-field cases."""

    section = "3.11"
    deterministic = True

    def score(self, record) -> list[Finding]:
        gold = record.gold
        expected_abst = gold.get("expected_abstention") or {}
        # Denominator: only cases that test an absent REQUIRED patient field.
        if expected_abst.get("reason_type") != "missing_patient_field":
            return []

        pc = record.patient_context
        required = gold.get("required_patient_fields", []) or []
        # Presence rule: absent iff the key does not exist.
        missing_fields = [f for f in required if f not in pc]

        if record.is_missing:
            return [self._finding(record, False, missing_fields, "no response")]

        abstention = record.abstention or {}
        named_field = abstention.get("missing_field")
        gap = (abstention.get("gap_description") or "").lower()
        named = bool(missing_fields) and (
            named_field in missing_fields
            or any(f.lower() in gap for f in missing_fields)
            or any(f.replace("_", " ") in gap for f in missing_fields)
        )

        detected = record.abstained and named
        why = (
            f"abstained and named missing field(s) {missing_fields}"
            if detected
            else f"failed to abstain-and-name; abstained={record.abstained}, named={named}"
        )
        return [self._finding(record, detected, missing_fields, why)]

    def _finding(self, record, passed, missing_fields, why) -> Finding:
        return Finding(
            section="3.11",
            failure_type="" if passed else "missing_patient_field_undetected",
            passed=passed,
            case_id=record.case_id,
            rationale=why,
            evidence={"missing_required_fields": missing_fields},
        )
