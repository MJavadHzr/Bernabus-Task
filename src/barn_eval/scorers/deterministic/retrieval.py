"""4.1 retrieval recall @ K.

K is pinned to the retrieved-set size and the ordering policy is recorded in the
run config. Where retrieval_score is null, ordering falls back to array order and
the run emits a warning.

Interpretation caveat carried into the report: the prototype receives its
documents as input rather than retrieving them, so retrieved_documents is fixed
at case-authoring time. A high value here must not be read as evidence about a
retrieval component.
"""

from __future__ import annotations

from ..base import Finding, Scorer


class RetrievalScorer(Scorer):
    """4.1 recall@K, K = retrieved-set size (there is no larger corpus to cut at)."""

    section = "retrieval-recall"
    deterministic = True

    def score(self, record) -> list[Finding]:
        findings: list[Finding] = []
        docs = record.retrieved_documents
        k = len(docs)  # K pinned to the retrieved-set size
        doc_ids = {d["source_id"] for d in docs}
        required = record.gold.get("required_evidence", []) or []

        # Null retrieval_score => ordering falls back to array order; warn (data note).
        if any(d.get("retrieval_score") is None for d in docs):
            findings.append(
                Finding(
                    section="retrieval-recall",
                    failure_type="null_retrieval_score",
                    passed=True,
                    counts_denominator=False,
                    case_id=record.case_id,
                    rationale="a document has null retrieval_score; ordering falls back to array order",
                )
            )

        for doc_id in required:
            present = doc_id in doc_ids  # K == set size, so top-K == whole set
            findings.append(
                Finding(
                    section="retrieval-recall",
                    failure_type="" if present else "required_doc_not_retrieved",
                    passed=present,
                    unit_id=doc_id,
                    case_id=record.case_id,
                    value=float(k),
                    rationale=f"required doc {doc_id} {'in' if present else 'absent from'} top-{k} retrieved set",
                    evidence={"k": k, "fixture_retrieval": True},
                )
            )
        return findings
