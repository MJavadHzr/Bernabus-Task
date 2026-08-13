"""Judge vs deterministic vs manual disagreement reporting (Part Two).

An LLM judge may be one component but never the only evaluator. Where a metric
has both a judge verdict and a reference (deterministic check, hand label, or
manual review), the disagreement rate is reported per metric - not silently
resolved in favour of either side.

Primary reference: evaluation_cases/groundability_audit.jsonl.
"""
