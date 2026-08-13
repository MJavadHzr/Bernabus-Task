"""JSONL loading with schema validation.

Every loader validates against src/barn_eval/contracts before returning. A record that
fails validation is reported with its case_id and line number and counted as a
load failure; it is never silently skipped (Part Two requirement 10).
"""


def load_cases(path):
    """Yield validated evaluation cases."""
    raise NotImplementedError


def load_responses(path):
    """Yield validated model responses."""
    raise NotImplementedError


def load_confirmations(path):
    """Yield validated human confirmation events."""
    raise NotImplementedError
