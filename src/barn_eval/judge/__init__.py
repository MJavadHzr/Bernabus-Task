"""LLM judge client, cache and versioned prompts.

Public surface:
  Judge, JudgeVerdict, JudgeError, JudgeConfigError, build_judge, judge, load_prompt
      the OpenRouter client and its injectable callable (client.py)
  cache_key
      content-addressed replay key - implemented and ready, but the replay path
      is intentionally NOT wired in this build (see cache.py)
"""

from .cache import cache_key
from .client import (
    Judge,
    JudgeConfigError,
    JudgeError,
    JudgeVerdict,
    build_judge,
    judge,
    load_prompt,
)

__all__ = [
    "Judge",
    "JudgeVerdict",
    "JudgeError",
    "JudgeConfigError",
    "build_judge",
    "judge",
    "load_prompt",
    "cache_key",
]
