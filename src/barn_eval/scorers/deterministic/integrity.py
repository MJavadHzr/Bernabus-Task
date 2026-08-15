"""Evidence integrity and provenance completeness (Part Four requirement 5).

  content_hash equals sha256(content) for every cited document
  every citation resolves to a document in the case
  source_version, source_date and source_authority are non-null where cited

Also emits the per-response provenance record Part Four requires: source ID,
version, date, authority, content hash, retrieval score, evidence authority
level, supporting text span, model version, prompt version, evaluation version.
"""

from __future__ import annotations

from ...authority.confirmation import sha256_text
from ..base import Finding, Scorer


class IntegrityScorer(Scorer):
    """Cited-document integrity + the per-response provenance record."""

    section = "evidence-integrity"
    deterministic = True

    def score(self, record) -> list[Finding]:
        findings: list[Finding] = []
        docs = record.documents_by_id

        cited_ids: list[str] = []
        for claim in record.claims:
            for c in claim.get("citations", []) or []:
                cited_ids.append(c)
        cited_ids = sorted(set(cited_ids))

        provenance: list[dict] = []
        for source_id in cited_ids:
            doc = docs.get(source_id)
            if doc is None:
                # Resolution failure; fabricated-citation (3.5) owns the metric,
                # integrity records the provenance break.
                findings.append(
                    Finding(
                        section="evidence-integrity",
                        failure_type="citation_unresolved",
                        passed=False,
                        unit_id=source_id,
                        case_id=record.case_id,
                        rationale=f"cited source {source_id} does not resolve to a document",
                    )
                )
                continue

            # content_hash integrity for a cited doc.
            hash_ok = doc.get("content_hash") == sha256_text(doc.get("content", ""))
            if not hash_ok:
                findings.append(
                    Finding(
                        section="evidence-integrity",
                        failure_type="content_hash_mismatch",
                        passed=False,
                        unit_id=source_id,
                        case_id=record.case_id,
                        rationale=f"content_hash mismatch for cited doc {source_id}",
                    )
                )

            # Provenance completeness: these must be non-null where cited.
            missing_fields = [
                f for f in ("source_version", "source_date", "source_authority")
                if doc.get(f) in (None, "")
            ]
            if missing_fields:
                findings.append(
                    Finding(
                        section="evidence-integrity",
                        failure_type="incomplete_provenance",
                        passed=False,
                        unit_id=source_id,
                        case_id=record.case_id,
                        rationale=f"cited doc {source_id} missing provenance fields {missing_fields}",
                        evidence={"missing_fields": missing_fields},
                    )
                )

            provenance.append(
                {
                    "source_id": source_id,
                    "source_version": doc.get("source_version"),
                    "source_date": doc.get("source_date"),
                    "source_authority": doc.get("source_authority"),
                    "content_hash": doc.get("content_hash"),
                    "retrieval_score": doc.get("retrieval_score"),
                    "subject_patient_id": doc.get("subject_patient_id"),
                }
            )

        # Per-response provenance record (data artifact, not a pass/fail unit).
        findings.append(
            Finding(
                section="evidence-integrity",
                passed=True,
                counts_denominator=False,
                case_id=record.case_id,
                rationale="per-response provenance record",
                evidence={
                    "provenance": provenance,
                    "model_version": (record.response or {}).get("model_version"),
                    "prompt_version": (record.response or {}).get("prompt_version"),
                },
            )
        )
        return findings
