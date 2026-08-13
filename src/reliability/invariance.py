"""Evaluator invariance testing. Block condition 3.14.5.

If a perturbation that preserves meaning changes a verdict, the evaluator is
unstable, and an unstable evaluator cannot certify anything - the release
decision is invalidated regardless of the system's measured scores.

Covers the LLM judge AND the evaluation-side preprocessor, which is versioned
under evaluation_version and can shift results with no change to the system
under test.
"""
