"""LLM judge client.

Records the judge model name and version and the prompt version on every call,
so a judge change is attributable in the run metadata rather than appearing as
a change in the system under test.

The judge is one component and never the only evaluator (Part Two): every
judge-scored metric is compared against a deterministic check, a reference label
or manual review, and disagreements are reported.
"""


def judge(prompt_name: str, payload: dict, prompt_version: str = "v1"):
    """Single judge call. Goes through the cache; never called directly by scorers."""
    raise NotImplementedError
