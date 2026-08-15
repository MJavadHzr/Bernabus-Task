"""Meaning-preserving perturbations for invariance testing (block condition 3.14.5).

Each perturbation rewrites the surface form of what the EVALUATOR consumes while
holding the meaning fixed:

  claim_order      order of claims within a response (and their order in answer_text)
  citation_format  citation id casing: doc_c001a -> DOC_C001A, applied CONSISTENTLY
                   to the claim's citations, the document's source_id and the
                   harness-computed supporting_spans keys, so the claim->document
                   join is preserved and only the spelling changes. This is exactly
                   the preprocessor's unresolved open question (annotate-only): a
                   stable evaluator must not flip a verdict on citation case alone.
  paraphrase       lexical, meaning-preserving rewrites of answer/claim text
                   (contractions, "the patient"<->"this patient", ...). Deterministic
                   and conservative on purpose - no LLM rewrite, so meaning cannot
                   drift and the test stays reproducible.
  whitespace       whitespace and punctuation jitter only (double spaces, trailing
                   period, newline). Pure formatting.

Every perturbation is a PURE function (record, seed) -> new EvaluationRecord: it
deep-copies the case and response so the baseline record is never mutated, and it
never changes a claim_id / instruction_id, so baseline and perturbed verdicts can
be aligned unit-for-unit downstream.

These perturb what the EVALUATOR reads. They are distinct from Part Seven
distribution shifts, which perturb what the SYSTEM reads and live under
evaluation_cases/shifted/.
"""

from __future__ import annotations

import copy
import random
import re
from typing import Callable

from ..harness.models import EvaluationRecord


def _clone(record: EvaluationRecord) -> EvaluationRecord:
    """A deep copy the perturbation can freely mutate. supporting_spans is copied
    too because citation_format has to remap its (claim_id, source_id) keys."""
    return EvaluationRecord(
        case=copy.deepcopy(record.case),
        response=copy.deepcopy(record.response),
        confirmations=copy.deepcopy(record.confirmations),
        status=record.status,
        run_metadata=record.run_metadata,
        supporting_spans=dict(record.supporting_spans),
    )


def _claims(record: EvaluationRecord) -> list:
    return (record.response or {}).get("claims") or []


# -- claim order -------------------------------------------------------------
def claim_order(record: EvaluationRecord, *, seed: int = 0) -> EvaluationRecord:
    """Deterministically shuffle the claims (and mirror the order in answer_text).

    A verdict about whether a claim is grounded/correct must not depend on where
    the claim sits in the list.
    """
    out = _clone(record)
    if not out.response:
        return out
    claims = _claims(out)
    if len(claims) < 2:
        return out
    order = list(range(len(claims)))
    random.Random(seed).shuffle(order)
    out.response["claims"] = [claims[i] for i in order]
    # Rebuild answer_text from the reordered claim texts when it was just their join.
    texts = [c.get("text", "") for c in out.response["claims"]]
    if texts and all(t for t in texts):
        out.response["answer_text"] = " ".join(texts)
    return out


# -- citation format ---------------------------------------------------------
def _remap_citation(cid: str) -> str:
    return cid.upper()


def citation_format(record: EvaluationRecord, *, seed: int = 0) -> EvaluationRecord:
    """Uppercase every citation id consistently across claims, documents and spans.

    The claim->document join is preserved (both sides are rewritten the same way),
    so the ONLY thing that changes is the spelling the judge sees. If a verdict
    flips, the evaluator is keying off citation case - the preprocessor open
    question made concrete.
    """
    out = _clone(record)
    docs = out.case.get("input", {}).get("retrieved_documents", []) or []
    for doc in docs:
        if "source_id" in doc:
            doc["source_id"] = _remap_citation(doc["source_id"])
    for claim in _claims(out):
        cites = claim.get("citations") or []
        claim["citations"] = [_remap_citation(c) for c in cites]
    # Keep the harness-computed spans addressable under the new ids.
    out.supporting_spans = {
        (claim_id, _remap_citation(src)): span
        for (claim_id, src), span in out.supporting_spans.items()
    }
    return out


# -- paraphrase --------------------------------------------------------------
# Conservative, clearly meaning-preserving lexical rewrites. Ordered longest-first
# so multi-word phrases win before their single-word substrings.
_PARAPHRASE_RULES: list[tuple[str, str]] = [
    (r"\bthe patient\b", "this patient"),
    (r"\bis not\b", "isn't"),
    (r"\bare not\b", "aren't"),
    (r"\bdoes not\b", "doesn't"),
    (r"\bcannot\b", "can't"),
    (r"\bit is\b", "it's"),
    (r"\bthere is\b", "there's"),
    (r"\bappears to be\b", "seems to be"),
    (r"\bhowever\b", "though"),
]


def _paraphrase_text(text: str, rng: random.Random) -> str:
    if not text:
        return text
    for pattern, repl in _PARAPHRASE_RULES:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    return text


def paraphrase(record: EvaluationRecord, *, seed: int = 0) -> EvaluationRecord:
    """Rewrite answer_text and each claim/abstention text with meaning-preserving
    lexical substitutions. Citations and claim_ids are untouched."""
    out = _clone(record)
    if not out.response:
        return out
    rng = random.Random(seed)
    if out.response.get("answer_text"):
        out.response["answer_text"] = _paraphrase_text(out.response["answer_text"], rng)
    for claim in _claims(out):
        if claim.get("text"):
            claim["text"] = _paraphrase_text(claim["text"], rng)
    abst = out.response.get("abstention")
    if isinstance(abst, dict) and abst.get("gap_description"):
        abst["gap_description"] = _paraphrase_text(abst["gap_description"], rng)
    return out


# -- whitespace / punctuation ------------------------------------------------
def _jitter_ws(text: str) -> str:
    if not text:
        return text
    text = re.sub(r"\s+", "  ", text.strip())  # collapse then double the spacing
    if not text.endswith((".", "!", "?")):
        text = text + "."
    return text


def whitespace(record: EvaluationRecord, *, seed: int = 0) -> EvaluationRecord:
    """Whitespace and trailing-punctuation jitter on the free text only."""
    out = _clone(record)
    if not out.response:
        return out
    if out.response.get("answer_text"):
        out.response["answer_text"] = _jitter_ws(out.response["answer_text"])
    for claim in _claims(out):
        if claim.get("text"):
            claim["text"] = _jitter_ws(claim["text"])
    return out


# Registry: name -> pure transform. The invariance driver iterates this.
PERTURBATIONS: dict[str, Callable[..., EvaluationRecord]] = {
    "claim_order": claim_order,
    "citation_format": citation_format,
    "paraphrase": paraphrase,
    "whitespace": whitespace,
}


def default_perturbations() -> dict[str, Callable[..., EvaluationRecord]]:
    """The four meaning-preserving perturbations, as a fresh dict."""
    return dict(PERTURBATIONS)
