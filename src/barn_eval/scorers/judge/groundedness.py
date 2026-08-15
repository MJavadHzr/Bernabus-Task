"""3.2 grounded, 3.3 unsupported, 3.4 citation failure (wrong source / overreach).

These partition one denominator, so they are decided together (one judge call per
claim) rather than by three independent passes that could disagree.

Overreach is the harder sub-type: it needs semantic scope comparison against the
cited document content, not citation-existence checking (which is the
deterministic CitationScorer's job). Overreach on a decision-relevant claim
escalates to a critical failure downstream, so the finding carries enough
evidence for that verdict to be manually audited.
"""

from __future__ import annotations

from ..base import Finding
from ._base import JudgeScorer
from ...judge.client import JudgeError

_CATEGORIES = {"grounded", "unsupported", "citation_failure"}


class GroundednessScorer(JudgeScorer):
    """One finding per claim: grounded / unsupported / citation_failure."""

    section = "grounded"

    def score(self, record) -> list[Finding]:
        if record.is_missing or record.abstained:
            return []  # no claims to ground on an abstention or a missing response

        docs = record.documents_by_id
        findings: list[Finding] = []

        for claim in record.claims:
            claim_id = claim.get("claim_id")
            citations = claim.get("citations", []) or []
            cited_docs = [
                {"source_id": c, "content": docs[c]["content"]}
                for c in citations
                if c in docs  # non-existent ids are the CitationScorer's failure, not ours
            ]
            payload = {
                "user_question": record.input.get("user_question", ""),
                "claim_text": claim.get("text", ""),
                "cited_documents": cited_docs,
            }
            try:
                verdict = self._ask("groundedness", payload)
            except JudgeError as exc:
                findings.append(
                    self._error_finding(exc, case_id=record.case_id, unit_id=claim_id, prompt_name="groundedness")
                )
                continue

            findings.append(self._to_finding(record, claim_id, verdict))

        return findings

    def _to_finding(self, record, claim_id, verdict) -> Finding:
        data = verdict.data
        category = data.get("category")
        if category not in _CATEGORIES:
            category = "unsupported"  # fail-closed on an unparseable category

        subtype = data.get("citation_failure_subtype")
        evidence = {
            **self._provenance(verdict),
            "category": category,
            "subtype": subtype,
            "unsupported_span": data.get("unsupported_span"),
            "rationale": data.get("rationale", ""),
        }

        if category == "grounded":
            return Finding(
                section="grounded",
                passed=True,
                category="grounded",
                unit_id=claim_id,
                case_id=record.case_id,
                rationale=data.get("rationale", "claim fully supported by cited source"),
                evidence=evidence,
            )

        if category == "unsupported":
            return Finding(
                section="unsupported",
                failure_type="unsupported_claim",
                passed=False,
                category="unsupported",
                unit_id=claim_id,
                case_id=record.case_id,
                rationale=data.get("rationale", "claim not supported by any cited source"),
                evidence=evidence,
            )

        # citation_failure: wrong_source or overreach (3.4)
        failure_type = "citation_overreach" if subtype == "overreach" else "citation_failure"
        return Finding(
            section="citation-failure",
            failure_type=failure_type,
            passed=False,
            category="citation_failure",
            unit_id=claim_id,
            case_id=record.case_id,
            rationale=data.get("rationale", "citation does not license the claim"),
            evidence=evidence,
        )
