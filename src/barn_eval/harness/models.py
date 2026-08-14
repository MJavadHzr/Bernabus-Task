"""Canonical in-memory records.

EvaluationRecord is the single object every scorer consumes: one case joined to
its response (and any confirmation events), plus harness-computed fields that
appear in neither input file.

Harness-computed, never authored (input contract 3):
  supporting_text_span   per claim x citation, enables overreach detection
  status                 "ok" | "missing_response"
  run metadata           evaluation_version, run_id, seed, timestamp

status exists so that a case with no response still produces a record. Nothing
is dropped from any denominator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from pydantic import BaseModel, ConfigDict

STATUS_OK = "ok"
STATUS_MISSING = "missing_response"


class RunMetadata(BaseModel):
    """Run-level provenance: model, prompt, evaluation and preprocessor versions,
    seed, response_source, timestamp, run_id.

    Recorded BEFORE any scorer executes so a run stays attributable even if it
    later fails (harness/runner.py owns this).
    """

    model_config = ConfigDict(protected_namespaces=())

    run_id: str
    seed: int
    evaluation_version: str
    timestamp: str
    response_source: str
    response_source_version: Optional[str] = None
    preprocessor_version: Optional[str] = None
    model_version: Optional[str] = None
    prompt_version: Optional[str] = None
    judge_model: Optional[str] = None
    experiment_id: Optional[str] = None


@dataclass
class EvaluationRecord:
    """One case joined to one response. Scorers read this and nothing else.

    `case` and `response` hold the schema-validated raw dicts. patient_context is
    kept as a raw dict on purpose: 3.11's presence rule is "a field is present iff
    its key exists", and only the untouched dict preserves that distinction.
    """

    case: dict
    response: Optional[dict] = None
    confirmations: list[dict] = field(default_factory=list)
    status: str = STATUS_OK
    run_metadata: Optional[RunMetadata] = None

    # Harness-computed, never authored. Keyed by (claim_id, source_id).
    supporting_spans: dict[tuple[str, str], str] = field(default_factory=dict)

    # -- case-side accessors -------------------------------------------------
    @property
    def case_id(self) -> str:
        return self.case["case_id"]

    @property
    def case_type(self) -> str:
        return self.case["case_type"]

    @property
    def adversarial_category(self) -> Optional[str]:
        return self.case.get("adversarial_category")

    @property
    def is_adversarial(self) -> bool:
        return self.case_type == "adversarial"

    @property
    def input(self) -> dict:
        return self.case["input"]

    @property
    def gold(self) -> dict:
        return self.case["gold"]

    @property
    def patient_context(self) -> dict:
        return self.input.get("patient_context", {})

    @property
    def retrieved_documents(self) -> list[dict]:
        return self.input["retrieved_documents"]

    @property
    def documents_by_id(self) -> dict[str, dict]:
        return {d["source_id"]: d for d in self.retrieved_documents}

    # -- response-side accessors --------------------------------------------
    @property
    def is_missing(self) -> bool:
        return self.status == STATUS_MISSING

    @property
    def abstained(self) -> bool:
        return bool(self.response) and bool(self.response.get("abstained"))

    @property
    def answered(self) -> bool:
        return self.response is not None and not self.response.get("abstained", False)

    @property
    def claims(self) -> list[dict]:
        return (self.response or {}).get("claims", []) or []

    @property
    def answer_text(self) -> str:
        return (self.response or {}).get("answer_text", "") or ""

    @property
    def abstention(self) -> Optional[dict]:
        return (self.response or {}).get("abstention")

    def claim_by_id(self, claim_id: str) -> Optional[dict]:
        for c in self.claims:
            if c.get("claim_id") == claim_id:
                return c
        return None
