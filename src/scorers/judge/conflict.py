"""3.9 conflict-handling accuracy.

  resolvable    a principled tiebreaker exists (authority, recency-within-tier,
                specificity) -> apply it WITH DISCLOSURE
  unresolvable  comparable authority/recency/relevance -> abstain, naming both
                positions as the gap

Silent resolution is never acceptable regardless of whether the pick was
correct, and is always critical-failure-eligible.

Reported with a sub-failure breakdown, because a single pass rate cannot
distinguish a governance failure (silent resolution) from an execution failure
(right process, wrong outcome).
"""
