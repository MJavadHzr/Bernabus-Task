"""Machine-readable output: case-level and aggregate, JSON and CSV.

Every loaded case appears in case-level output, including status
"missing_response". Nothing is dropped from any denominator, and the run exits
non-zero when the missing count is above zero.
"""
