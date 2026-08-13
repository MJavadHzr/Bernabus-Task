"""3.10 staleness-handling accuracy.

Newer wins on the relevant clock, with disclosure. Staleness is subordinate to
authority: a newer low-tier document never overrides an older high-tier one -
that is an authority question, not a staleness question.

Sub-failure types, separable only because gold declares wrong_clock_conclusion:
  wrong clock used entirely            conclusion matches wrong_clock_conclusion
  right clock, tier subordination      matches neither, lower tier preferred
  right clock and tier, no disclosure

Residual limitation: reasoning is unobserved, so "used the right clock" is
inferred from the conclusion. A system reaching the right answer by the wrong
route scores as a pass.
"""
