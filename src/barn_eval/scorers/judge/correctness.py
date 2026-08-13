"""3.1 correct answer rate.

Compares the final conclusion against gold.expected_conclusion. Scored only on
answered cases. Judged on the CONCLUSION, not the reasoning - reasoning quality
is groundedness's job, and fluency is scored separately from both.

Limitation carried into the report: this does not catch a right conclusion
reached through ungrounded or fabricated reasoning, so it is never reported
without groundedness beside it.
"""
