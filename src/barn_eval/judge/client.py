"""LLM judge client (OpenRouter, OpenAI-compatible /chat/completions).

Records the judge model name and the prompt version on every call, so a judge
change is attributable in the run metadata rather than appearing as a change in
the system under test.

The judge is one component and never the only evaluator (Part Two): every
judge-scored metric is compared against a deterministic check, a reference label
or manual review, and disagreements are reported.

REPRODUCIBILITY NOTE (v1, cache deliberately skipped):
  Temperature is pinned to 0, which is necessary but NOT sufficient for a
  bit-reproducible run - a live judge can still drift between runs. The
  content-addressed replay cache (judge/cache.py) is the mechanism that closes
  that gap and is intentionally OFF the call path for now. Everything is routed
  through the single `Judge.__call__` seam so the cache can be reinstated in one
  place later without touching any scorer.

Transport is the OpenAI SDK pointed at OpenRouter's OpenAI-compatible endpoint.
The SDK is used for its automatic retry/backoff (the free tier 429s often), typed
errors and connection pooling across the many per-claim calls; the key is still
read only from the environment, never hardcoded.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

_PROMPTS_ROOT = Path(__file__).resolve().parent / "prompts"


class JudgeError(RuntimeError):
    """Any failure to obtain a usable verdict. Scorers treat this fail-closed."""


class JudgeConfigError(JudgeError):
    """Misconfiguration: missing API key, unknown prompt, replay-only with no cache."""


@dataclass
class JudgeVerdict:
    """A parsed judge response plus the provenance every scorer records.

    `data` is the model's JSON object (the verdict the scorer reasons over).
    `model` and `prompt_version` are stamped onto every Finding.evidence so a
    later judge/prompt change is visible in the numbers' provenance.
    """

    data: dict
    model: str
    prompt_name: str
    prompt_version: str
    raw: str = ""


@lru_cache(maxsize=None)
def load_prompt(prompt_name: str, prompt_version: str = "v1") -> str:
    """Read prompts/<version>/<name>.md. The directory name IS the prompt version."""
    path = _PROMPTS_ROOT / prompt_version / f"{prompt_name}.md"
    if not path.exists():
        raise JudgeConfigError(f"judge prompt not found: {path}")
    return path.read_text(encoding="utf-8")


def _extract_json(content: str) -> dict:
    """Pull the first JSON object out of a model completion.

    Reasoning models wrap the answer in prose or ```json fences; we tolerate both
    by taking the outermost {...} span. A completion with no object is a hard
    error (fail-closed), never a silent empty verdict.
    """
    text = content.strip()
    if text.startswith("```"):
        # strip a leading ```json / ``` fence and its closing fence
        text = text.split("```", 2)
        text = text[1] if len(text) > 1 else content
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise JudgeError(f"no JSON object in judge completion: {content[:200]!r}")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise JudgeError(f"judge completion is not valid JSON: {exc}") from exc


@dataclass
class Judge:
    """A configured, callable judge. Injected into judge scorers; never global.

    Callable contract used by every judge scorer:
        verdict = judge(prompt_name, payload)   # -> JudgeVerdict

    The runner (Part Eight) builds one Judge from config and injects it into the
    judge scorers. Tests inject a scripted fake with the same call signature, so
    no scorer test ever touches the network.
    """

    model: str
    base_url: str = "https://openrouter.ai/api/v1"
    api_key_env: str = "OPENROUTER_API_KEY"
    prompt_version: str = "v1"
    temperature: float = 0.0
    timeout: float = 120.0
    # Generous by default: a reasoning model's chain-of-thought counts toward this
    # on OpenRouter, so too low a cap truncates the run before the JSON verdict.
    max_tokens: int = 4096
    max_retries: int = 4
    extra_headers: dict[str, str] = field(
        default_factory=lambda: {
            # Optional OpenRouter attribution headers; harmless if ignored.
            "HTTP-Referer": "https://local/barn-ais-eval-001",
            "X-Title": "BARN-AIS-EVAL-001 judge",
        }
    )
    _client: object = field(default=None, init=False, repr=False, compare=False)

    def __call__(self, prompt_name: str, payload: dict) -> JudgeVerdict:
        system = load_prompt(prompt_name, self.prompt_version)
        content = self._complete(system, json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return JudgeVerdict(
            data=_extract_json(content),
            model=self.model,
            prompt_name=prompt_name,
            prompt_version=self.prompt_version,
            raw=content,
        )

    # -- transport (OpenAI SDK -> OpenRouter) --------------------------------
    def _api_key(self) -> str:
        key = os.environ.get(self.api_key_env)
        if not key:
            raise JudgeConfigError(
                f"judge API key not set: export {self.api_key_env} "
                f"(provider endpoint {self.base_url})"
            )
        return key

    def _openai(self):
        """Lazily build the SDK client. The key is resolved here, from the
        environment only, so an unset key fails on first use rather than at
        construction and is never captured anywhere but the client instance."""
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:  # pragma: no cover - packaging guard
                raise JudgeConfigError(
                    "the OpenAI SDK is required for live judging: pip install '.[judge]'"
                ) from exc
            self._client = OpenAI(
                base_url=self.base_url,
                api_key=self._api_key(),
                timeout=self.timeout,
                max_retries=self.max_retries,  # automatic backoff on 429/5xx
                default_headers=self.extra_headers,
            )
        return self._client

    def _complete(self, system: str, user: str) -> str:
        try:
            from openai import OpenAIError
        except ImportError:  # pragma: no cover - packaging guard
            OpenAIError = Exception  # type: ignore[assignment]
        try:
            resp = self._openai().chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
        except OpenAIError as exc:  # pragma: no cover - network path
            raise JudgeError(f"judge request failed: {exc}") from exc
        try:
            return resp.choices[0].message.content or ""
        except (AttributeError, IndexError, TypeError) as exc:  # pragma: no cover
            raise JudgeError(f"unexpected judge response shape: {resp!r}") from exc


def build_judge(judge_cfg: dict) -> Judge:
    """Construct a Judge from the `judge:` block of run config.

    Honours `enabled`/`replay_only`: replay-only with no cache on the path is a
    configuration error rather than a silent live call, so a reviewer who asked
    for offline replay is told the cache is not wired instead of being billed.
    """
    if not judge_cfg.get("enabled", True):
        raise JudgeConfigError("judge is disabled in config (judge.enabled=false)")
    if judge_cfg.get("replay_only"):
        raise JudgeConfigError(
            "judge.replay_only=true but the replay cache is not on the call path "
            "in this build; set replay_only=false to allow live judge calls"
        )
    model = judge_cfg.get("model")
    if not model:
        raise JudgeConfigError("judge.model is required")
    kwargs = dict(
        model=model,
        base_url=judge_cfg.get("base_url", "https://openrouter.ai/api/v1"),
        api_key_env=judge_cfg.get("api_key_env", "OPENROUTER_API_KEY"),
        prompt_version=judge_cfg.get("prompt_version", "v1"),
        temperature=float(judge_cfg.get("temperature", 0.0)),
    )
    # Reasoning models spend tokens thinking before the JSON verdict, and on
    # OpenRouter those count toward max_tokens - so it is config-driven and
    # generous by default rather than pinned low.
    if judge_cfg.get("max_tokens") is not None:
        kwargs["max_tokens"] = int(judge_cfg["max_tokens"])
    if judge_cfg.get("timeout") is not None:
        kwargs["timeout"] = float(judge_cfg["timeout"])
    if judge_cfg.get("max_retries") is not None:
        kwargs["max_retries"] = int(judge_cfg["max_retries"])
    return Judge(**kwargs)


_DEFAULT_JUDGE: Optional[Judge] = None


def judge(prompt_name: str, payload: dict, prompt_version: str = "v1") -> JudgeVerdict:
    """Single judge call via a process-default Judge. Never called by scorers.

    Scorers receive an injected judge; this module-level entrypoint exists for
    ad-hoc use and for the runner before config wiring. It reads the model from
    OPENROUTER_MODEL (falling back to the documented free default).
    """
    global _DEFAULT_JUDGE
    if _DEFAULT_JUDGE is None or _DEFAULT_JUDGE.prompt_version != prompt_version:
        _DEFAULT_JUDGE = Judge(
            model=os.environ.get("OPENROUTER_MODEL", "nvidia/nemotron-3-super-120b-a12b:free"),
            prompt_version=prompt_version,
        )
    return _DEFAULT_JUDGE(prompt_name, payload)
