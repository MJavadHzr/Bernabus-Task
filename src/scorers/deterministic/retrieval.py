"""4.1 retrieval recall @ K.

K is pinned to the retrieved-set size and the ordering policy is recorded in the
run config. Where retrieval_score is null, ordering falls back to array order and
the run emits a warning.

Interpretation caveat carried into the report: the prototype receives its
documents as input rather than retrieving them, so retrieved_documents is fixed
at case-authoring time. A high value here must not be read as evidence about a
retrieval component.
"""
