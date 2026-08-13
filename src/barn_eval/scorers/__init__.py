"""Scorer registry, split by determinism rather than by metric family.

This directory listing IS the 5 exemption list: everything under
deterministic/ is exempt from the evaluate-the-evaluator burden, everything
under judge/ is subject to it and can, if unstable, invalidate the release
decision regardless of the system's scores.

A metric filed in the wrong directory is visible in review rather than buried
in a docstring.
"""
