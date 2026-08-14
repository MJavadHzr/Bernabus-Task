"""Run configuration loading and path resolution.

A run must be reconstructible from config + git SHA alone (see run.default.yaml),
so this module only *reads* the frozen config and resolves its relative paths - it
never injects defaults that would change a number without appearing in the file.

Paths in the config are relative to the repository root (the parent of configs/),
resolved here to absolute paths so the runner is independent of the working
directory.
"""

from __future__ import annotations

import glob
from pathlib import Path

import yaml


def load_config(path: str | Path) -> dict:
    """Read a run config and stamp the resolved repo root under `_base_dir`."""
    cfg_path = Path(path).resolve()
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    # configs/run.default.yaml -> configs/ -> repo root
    raw["_base_dir"] = str(cfg_path.parent.parent)
    raw["_config_path"] = str(cfg_path)
    return raw


def resolve(config: dict, rel: str) -> Path:
    """Resolve one config-relative path against the repo root."""
    p = Path(rel)
    return p if p.is_absolute() else Path(config["_base_dir"]) / p


def resolve_globs(config: dict, patterns: list[str]) -> list[Path]:
    """Expand a list of path patterns (globs allowed), sorted and de-duplicated.

    A glob that matches nothing is kept as its literal path so the loader reports
    a missing file rather than silently evaluating an empty suite.
    """
    out: list[Path] = []
    seen: set[str] = set()
    for pattern in patterns:
        base = resolve(config, pattern)
        matches = sorted(glob.glob(str(base))) or [str(base)]
        for m in matches:
            if m not in seen:
                seen.add(m)
                out.append(Path(m))
    return out
