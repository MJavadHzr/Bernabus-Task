"""Rate computation. Pooled and per-case-averaged, for every rate metric.

Per-case-averaged is the primary safety-facing number: it surfaces single bad
cases more aggressively than a pooled figure can, because pooling lets a large
well-behaved case dilute a small catastrophic one.

Contains no gate logic. See gates.py for why that separation is physical.
"""
