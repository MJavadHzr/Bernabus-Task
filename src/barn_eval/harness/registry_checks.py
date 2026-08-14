"""Load-time preconditions. Fail loud, fail before scoring.

These turn stated limitations into enforced invariants, so a badly-formed case
is rejected rather than producing a coincidental pass.

  patient_context is a verbatim subset of data/synthetic/synthetic_patients.json
  required_evidence source_ids all exist in the case's retrieved_documents
  content_hash matches sha256(content) for every document
  contamination probe_facts appear in no other retrieved doc and not in context
  discriminating_clocks genuinely reorder the documents (3.10)
  expected_abstention present whenever expected_behavior == "abstain"
  required_patient_fields drawn only from the closed patient vocabulary
  case_id uniqueness across every loaded file
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Optional

# Closed patient vocabulary, mirrored from evaluation_case.schema.json #/definitions/patient_field.
CLOSED_PATIENT_FIELDS = frozenset(
    {
        "patient_id",
        "display_name",
        "age",
        "sex",
        "known_conditions",
        "current_medications",
        "allergies",
        "baseline_labs",
        "visit_history",
    }
)


@dataclass
class RegistryViolation:
    """One precondition failure, attributable to a specific case and check."""

    case_id: str
    check: str
    message: str


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _clock_value(doc: dict, clock: str) -> Optional[str]:
    """Return the timestamp string for a clock, or source_date fallback, or None."""
    ts = doc.get("timestamps") or {}
    val = ts.get(clock)
    if val is not None:
        return val
    # Part One 3.10: sources with no clinical clock map to source_date.
    return doc.get("source_date")


def _appears_in(fact: str, text: str) -> bool:
    return fact.strip().lower() in (text or "").lower()


def check_registry(cases, patients) -> list[RegistryViolation]:
    """Return a list of precondition violations. Empty list means the suite loads."""
    patients_list = patients.get("patients", []) if isinstance(patients, dict) else list(patients)
    patients_by_id = {p["patient_id"]: p for p in patients_list}

    violations: list[RegistryViolation] = []
    seen_case_ids: set[str] = set()

    for case in cases:
        cid = case.get("case_id", "<unknown>")
        if cid in seen_case_ids:
            violations.append(
                RegistryViolation(cid, "case_id_uniqueness", f"duplicate case_id {cid!r}")
            )
        seen_case_ids.add(cid)

        inp = case.get("input", {})
        gold = case.get("gold", {})
        pc = inp.get("patient_context", {})
        docs = inp.get("retrieved_documents", [])
        docs_by_id = {d["source_id"]: d for d in docs}

        # 1. patient_context is a verbatim subset of the registry.
        pid = pc.get("patient_id")
        if pc:
            if pid is None:
                violations.append(
                    RegistryViolation(cid, "patient_registry", "patient_context has no patient_id")
                )
            else:
                reg = patients_by_id.get(pid)
                if reg is None:
                    violations.append(
                        RegistryViolation(
                            cid, "patient_registry", f"patient_id {pid!r} not in registry"
                        )
                    )
                else:
                    for key, value in pc.items():
                        if key not in reg or reg[key] != value:
                            violations.append(
                                RegistryViolation(
                                    cid,
                                    "patient_context_subset",
                                    f"field {key!r} is not a verbatim subset of registry patient {pid!r}",
                                )
                            )

        # 2. required_evidence source_ids all exist in retrieved_documents.
        for sid in gold.get("required_evidence", []):
            if sid not in docs_by_id:
                violations.append(
                    RegistryViolation(
                        cid,
                        "required_evidence_exists",
                        f"required_evidence {sid!r} not in retrieved_documents",
                    )
                )

        # 3. content_hash matches sha256(content) for every document.
        for d in docs:
            expected = _sha256(d.get("content", ""))
            if d.get("content_hash") != expected:
                violations.append(
                    RegistryViolation(
                        cid,
                        "content_hash",
                        f"content_hash mismatch for {d.get('source_id')!r}",
                    )
                )

        # 4. contamination probe_facts appear in no OTHER retrieved doc and not in context.
        probe = gold.get("contamination_probe")
        if probe:
            foreign = probe.get("foreign_doc_id")
            pc_blob = json.dumps(pc, ensure_ascii=False)
            for fact in probe.get("probe_facts", []):
                for d in docs:
                    if d.get("source_id") == foreign:
                        continue
                    if _appears_in(fact, d.get("content", "")):
                        violations.append(
                            RegistryViolation(
                                cid,
                                "probe_fact_isolation",
                                f"probe_fact {fact!r} leaks into non-foreign doc {d.get('source_id')!r}",
                            )
                        )
                if _appears_in(fact, pc_blob):
                    violations.append(
                        RegistryViolation(
                            cid,
                            "probe_fact_isolation",
                            f"probe_fact {fact!r} appears in patient_context",
                        )
                    )

        # 5. discriminating_clocks genuinely reorder the two staleness documents.
        stale = gold.get("evidence_staleness") or {}
        if stale.get("present") and stale.get("discriminating_clocks"):
            clocks = stale["discriminating_clocks"]
            a = docs_by_id.get(stale.get("stale_doc_id"))
            b = docs_by_id.get(stale.get("current_doc_id"))
            if a is None or b is None:
                violations.append(
                    RegistryViolation(
                        cid,
                        "discriminating_clocks",
                        "stale_doc_id/current_doc_id do not resolve to retrieved documents",
                    )
                )
            else:
                orders = []
                for clock in clocks:
                    va, vb = _clock_value(a, clock), _clock_value(b, clock)
                    if va is None or vb is None or va == vb:
                        orders.append(None)
                    else:
                        orders.append(va < vb)  # True => a older than b on this clock
                if None in orders or orders[0] == orders[1]:
                    violations.append(
                        RegistryViolation(
                            cid,
                            "discriminating_clocks",
                            f"clocks {clocks} do not reorder the documents",
                        )
                    )

        # 6. expected_abstention present whenever expected_behavior == "abstain".
        if gold.get("expected_behavior") == "abstain" and "expected_abstention" not in gold:
            violations.append(
                RegistryViolation(
                    cid,
                    "expected_abstention_present",
                    "expected_behavior is 'abstain' but gold.expected_abstention is absent",
                )
            )

        # 7. required_patient_fields drawn only from the closed vocabulary.
        for f in gold.get("required_patient_fields", []):
            if f not in CLOSED_PATIENT_FIELDS:
                violations.append(
                    RegistryViolation(
                        cid,
                        "required_patient_fields_vocab",
                        f"required_patient_field {f!r} not in the closed patient vocabulary",
                    )
                )

    return violations
