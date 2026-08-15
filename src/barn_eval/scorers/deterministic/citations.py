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

from __future__ import annotations

from ..base import Finding, Scorer


class CitationScorer(Scorer):
    """Emits findings for 3.5 (fabricated), 4.3 (recall), and the existence half of 4.2."""

    section = "fabricated-citation"
    deterministic = True

    def score(self, record) -> list[Finding]:
        findings: list[Finding] = []
        docs = record.documents_by_id

        # -- 3.5 fabricated citation (claim-level) + 4.2 existence half (citation-level)
        cited_ids: set[str] = set()
        for claim in record.claims:
            claim_id = claim.get("claim_id")
            citations = claim.get("citations", []) or []
            missing = [c for c in citations if c not in docs]
            for c in citations:
                cited_ids.add(c)
                # 4.2 existence half: a citation to a non-existent source is imprecise.
                findings.append(
                    Finding(
                        section="citation-precision",
                        failure_type="" if c in docs else "citation_nonexistent",
                        passed=c in docs,
                        unit_id=c,
                        case_id=record.case_id,
                        rationale="citation-precision existence half; relevance is judge-side",
                        evidence={"claim_id": claim_id, "source_id": c},
                    )
                )
            # 3.5 fabricated: a claim carrying any non-existent source id.
            findings.append(
                Finding(
                    section="fabricated-citation",
                    failure_type="fabricated_citation" if missing else "",
                    passed=not missing,
                    unit_id=claim_id,
                    case_id=record.case_id,
                    rationale=(
                        f"cited source id(s) absent from retrieved set: {missing}"
                        if missing
                        else "all cited source ids exist"
                    ),
                    evidence={"missing_source_ids": missing, "citations": citations},
                )
            )

        # -- 4.3 citation recall (document-level, against gold.required_evidence)
        required = record.gold.get("required_evidence", []) or []
        for doc_id in required:
            present = doc_id in cited_ids
            findings.append(
                Finding(
                    section="citation-recall",
                    failure_type="" if present else "missing_required_citation",
                    passed=present,
                    unit_id=doc_id,
                    case_id=record.case_id,
                    rationale=(
                        f"required evidence {doc_id} cited"
                        if present
                        else f"required evidence {doc_id} not cited (applies to abstentions too)"
                    ),
                    evidence={"required_evidence": doc_id, "cited_ids": sorted(cited_ids)},
                )
            )

        return findings
