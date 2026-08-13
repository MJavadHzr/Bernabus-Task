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


def check_registry(cases, patients):
    """Return a list of precondition violations. Empty list means the suite loads."""
    raise NotImplementedError
