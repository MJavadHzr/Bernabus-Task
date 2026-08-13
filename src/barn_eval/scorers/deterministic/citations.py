"""3.5 fabricated citation, 4.2 citation precision, 4.3 citation recall.

Fabricated citation is a source-ID existence check against the case's
retrieved_documents. Deterministic and exact; the limitation is on tolerance,
not detection - any non-zero rate on a decision-relevant claim blocks release.

Citation recall is measured at DOCUMENT level against gold.required_evidence,
because gold cannot reference claim_ids that do not exist until the system
responds. It applies to abstentions too: where a case's evidence documents the
absence of a fact, citing it is what separates an abstention that checked the
evidence from one that defaulted.

The relevance half of citation precision requires semantic judgment and lives in
scorers/judge/groundedness.py. Only the existence half is decided here.
"""
