"""The extractors by name, for the command line and the benchmark.

One place to add a new one. Model extractors are wrapped in the proposal cache
and share one `Budget`, so a run's spend is capped and reported.
"""
from __future__ import annotations

import os

from proven.budget import Budget
from proven.cache import CachedExtractor
from proven.extract import RuleExtractor

NAMES = ("rules", "claude")


def build(name: str = "rules", *, model: str | None = None, budget: Budget | None = None,
          cache_dir: str | None = ".proven/cache"):
    if cache_dir == ".proven/cache":
        cache_dir = os.environ.get("PROVEN_CACHE_DIR") or cache_dir
    if name == "rules":
        return RuleExtractor()
    if name == "claude":
        from proven.llm import MODEL, ClaudeExtractor
        inner = ClaudeExtractor(model=model or os.environ.get("PROVEN_CLAUDE_MODEL") or MODEL,
                                budget=budget or Budget())
    else:
        raise ValueError(f"unknown extractor {name!r}; choose from {', '.join(NAMES)}")
    return CachedExtractor(inner, cache_dir) if cache_dir else inner
