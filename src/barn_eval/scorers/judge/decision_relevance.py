"""Decision-relevance determination against gold.decision_relevant_criteria.

A claim is decision-relevant if its falsification or reversal would change the
clinical action a reasonable clinician takes.

This is the highest-leverage judge call in the framework: after the v1.1
collapse of 3.12 item 5, decision_relevant_criteria is GATE-FIRING. An
over-broad criterion widens the set of claims on which a scope expansion blocks
release. Disagreement here propagates into every critical-failure verdict.
"""
