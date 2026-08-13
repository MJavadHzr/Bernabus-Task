"""Load-time preconditions reject malformed cases (src/harness/registry_checks.py).

A case that fails a precondition must be rejected before scoring, not allowed to
produce a coincidental pass.
"""
