"""Join semantics (input contract 4).

  join key                 case_id, exact match
  case without response    status="missing_response", counted loudly, non-zero exit
  response without case    data-integrity error: logged and excluded
  confirmations            joined on case_id + claim_id, many-to-one

Evaluation continues past a missing response. It does not continue past a
response that cannot be attributed to a case.
"""


def join(cases, responses, confirmations=None):
    """Return EvaluationRecords, one per case, plus a join report."""
    raise NotImplementedError
