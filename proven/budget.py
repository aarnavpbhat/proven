"""A hard cap on what a model extractor may spend in one process.

The cap is checked before every request, so a run stops at the limit rather
than reporting afterwards that it went over. Tokens are counted from the
provider's own usage figures. With several workers, requests already in flight
when the cap is reached still complete, so the overshoot is at most one request
per worker.
"""
from __future__ import annotations

import os
import threading

DEFAULT_MAX_TOKENS = 300_000


class BudgetExceeded(RuntimeError):
    """The process has used its token budget; no further request was sent."""


class Budget:
    """A cap on tokens and dollars for one run; a request past the cap raises BudgetExceeded."""
    def __init__(self, max_tokens: int | None = None, max_usd: float | None = None):
        if max_tokens is None:
            max_tokens = int(os.environ.get("PROVEN_TOKEN_BUDGET") or DEFAULT_MAX_TOKENS)
        if max_usd is None and os.environ.get("PROVEN_USD_BUDGET"):
            max_usd = float(os.environ["PROVEN_USD_BUDGET"])
        self.max_tokens = max_tokens
        self.max_usd = max_usd
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.usd = 0.0
        self._lock = threading.Lock()

    @property
    def tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def check(self) -> None:
        with self._lock:
            if self.tokens >= self.max_tokens:
                raise BudgetExceeded(
                    f"token budget reached: {self.tokens:,} of {self.max_tokens:,} used in "
                    f"{self.calls} request(s); raise it with --token-budget or PROVEN_TOKEN_BUDGET")
            if self.max_usd is not None and self.usd >= self.max_usd:
                raise BudgetExceeded(
                    f"spend budget reached: ${self.usd:.2f} of ${self.max_usd:.2f} used in "
                    f"{self.calls} request(s); raise it with PROVEN_USD_BUDGET")

    def add(self, input_tokens: int, output_tokens: int, usd: float = 0.0) -> None:
        with self._lock:
            self.calls += 1
            self.input_tokens += int(input_tokens or 0)
            self.output_tokens += int(output_tokens or 0)
            self.usd += usd

    def to_dict(self) -> dict:
        return {"calls": self.calls, "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens, "tokens": self.tokens,
                "max_tokens": self.max_tokens, "usd": round(self.usd, 4),
                "max_usd": self.max_usd}
