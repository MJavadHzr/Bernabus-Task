"""Semantic judgments. Every scorer here is subject to the 5 reliability
requirement, and instability in any of them is block condition 3.14.5 -
which takes precedence over any score the system under test receives.

Each must be compared against a deterministic check, a reference label or manual
review, with disagreements reported (Part Two, "on LLM judges").
"""
