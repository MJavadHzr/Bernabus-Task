"""Join semantics (input contract 4).

  join key                 case_id, exact match
  case without response    status="missing_response", counted loudly, non-zero exit
  response without case    data-integrity error: logged and excluded
  confirmations            joined on case_id + claim_id, many-to-one

Evaluation continues past a missing response. It does not continue past a
response that cannot be attributed to a case.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import STATUS_MISSING, STATUS_OK, EvaluationRecord


@dataclass
class JoinReport:
    """What the join found, kept loud so nothing vanishes into a denominator."""

    total_cases: int = 0
    joined: int = 0
    missing_response: list[str] = field(default_factory=list)   # case_ids with no response
    orphan_responses: list[str] = field(default_factory=list)   # response case_ids with no case
    duplicate_responses: list[str] = field(default_factory=list)  # case_ids seen more than once

    @property
    def has_missing(self) -> bool:
        return bool(self.missing_response)

    @property
    def has_integrity_error(self) -> bool:
        return bool(self.orphan_responses) or bool(self.duplicate_responses)


def join(cases, responses, confirmations=None) -> tuple[list[EvaluationRecord], JoinReport]:
    """Return EvaluationRecords, one per case, plus a join report.

    One record is produced for every case, including cases with no response
    (status="missing_response"). Orphan responses (no matching case) are excluded
    and reported as data-integrity errors, never scored against absent gold.
    """
    cases = list(cases)
    responses = list(responses)
    confirmations = list(confirmations or [])

    case_ids = {c["case_id"] for c in cases}

    # First response wins; a repeat is a data-integrity signal, not a silent overwrite.
    responses_by_case: dict[str, dict] = {}
    duplicates: list[str] = []
    orphans: list[str] = []
    for r in responses:
        cid = r["case_id"]
        if cid not in case_ids:
            orphans.append(cid)
            continue
        if cid in responses_by_case:
            duplicates.append(cid)
            continue
        responses_by_case[cid] = r

    # Confirmations grouped by case_id (claim-level match happens in authority/).
    confs_by_case: dict[str, list[dict]] = {}
    for cf in confirmations:
        confs_by_case.setdefault(cf["case_id"], []).append(cf)

    records: list[EvaluationRecord] = []
    report = JoinReport(total_cases=len(cases))
    for c in cases:
        cid = c["case_id"]
        resp = responses_by_case.get(cid)
        status = STATUS_OK if resp is not None else STATUS_MISSING
        if resp is None:
            report.missing_response.append(cid)
        else:
            report.joined += 1
        records.append(
            EvaluationRecord(
                case=c,
                response=resp,
                confirmations=confs_by_case.get(cid, []),
                status=status,
            )
        )

    report.orphan_responses = sorted(set(orphans))
    report.duplicate_responses = sorted(set(duplicates))
    return records, report
