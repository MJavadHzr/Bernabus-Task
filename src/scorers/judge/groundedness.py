"""3.2 grounded, 3.3 unsupported, 3.4 citation failure (wrong source / overreach).

These partition one denominator, so they are decided together rather than by
three independent passes that could disagree with each other.

Groundability sets that denominator and is not declared anywhere in the schema -
the single largest judge dependency in the framework. Mitigated, not removed, by
evaluation_cases/groundability_audit.jsonl, against which the judge's
classification is compared and disagreements reported.

Overreach is the harder sub-type: it needs semantic scope comparison against the
supporting_text_span, not citation-existence checking. It is also the sub-type
that now escalates to a critical failure on a decision-relevant claim, so every
overreach verdict is manually audited before it is allowed to block a release.
"""
