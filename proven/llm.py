"""An optional extractor backed by Claude. It proposes; it never decides.

WHAT THE MODEL IS FOR

The rule extractor reads the phrasings it was written for. Commentary in the
wild is written in every other way too, and the benchmark measures what that
costs: on held-out phrasing, binding a stated reason to transactions by words
alone decides almost nothing. A language model reads the sentence the way a
person would — which account it means, which words state the change, which
words state the cause — and suggests vocabulary a cause might leave in a ledger.

WHAT THE MODEL MAY NOT DO

Everything it returns is a `ClaimProposal` and goes through `claims.admit()`:
the quote must be verbatim, every figure must be in the quote, direction and
attribution strength are re-read from the words, and an account it maps without
an alias in the sentence is marked as its mapping. Its search terms are marked
`model`; `verify.py` will not let a claim pass on the strength of those terms
alone, nor decide a claim whose account only the model chose. The output schema
has no field for a verdict, a status or a severity, so there is nowhere for one
to hide.

WHAT LEAVES THE MACHINE

Only the explanation text and the chart of accounts (names and aliases). No
transaction, vendor, memo or amount is ever sent, so the model cannot be asked
— or tempted — to check anything. Every request is recorded on the run: the
model, the byte count, a hash of the payload, and the list of what was and was
not included. The call is refused outright unless the process was started with
the network explicitly allowed (see `netguard.py`).

THE REQUEST

`client.beta.messages.create` with structured output (`output_config.format`,
a JSON schema) and adaptive thinking at `low` effort: this is a short
extraction, and effort is the documented lever for thinking spend on these
models (thinking cannot be turned off on Opus 5.5 or Sonnet 5.5). `max_tokens`
is a ceiling, not a charge; a reply that hits it is recorded and yields
nothing. Models with server-side refusal fallback (Opus 5.5, Sonnet 5.5) opt in
with `fallbacks="default"` under the `server-side-fallback-2026-07-01` beta, so
a classifier refusal is retried on Anthropic's recommended fallback model.
Claude Haiku 5.5 has no server-side fallback, so its requests carry neither the
parameter nor the beta. A refusal that survives produces no proposals and is
recorded.

WHAT IT COSTS

Every request is priced from the provider's own usage figures with `PRICES`
(USD per million tokens, from Anthropic's pricing page, November 2026): base
input, 5-minute and 1-hour cache writes, cache reads and output. Thinking is
billed as output and is already inside `output_tokens`. When a fallback ran,
`usage.iterations` lists each attempt with the model that ran it, and each is
priced at that model's rates. A model missing from the table is priced at the
highest rates in it, so spend is never under-counted.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
from datetime import datetime, timezone
from typing import Any

from proven import netguard
from proven.budget import Budget
from proven.claims import ClaimProposal
from proven.ledger import Ledger

NAME = "claude"
VERSION = "0.2"
MODEL = "claude-opus-5-5"
EFFORT = "low"
MAX_TOKENS = 8000
FALLBACK_BETA = "server-side-fallback-2026-07-01"

# USD per million tokens: (input, 5m cache write, 1h cache write, cache read, output).
# Source: platform.claude.com/docs/en/about-claude/pricing, read 2026-11-09.
PRICES: dict[str, tuple[float, float, float, float, float]] = {
    "claude-opus-5-5": (4.00, 5.00, 8.00, 0.20, 20.00),
    "claude-sonnet-5-5": (2.00, 2.50, 4.00, 0.10, 10.00),
    "claude-haiku-5-5": (0.10, 0.125, 0.20, 0.01, 0.50),
    # possible server-side fallback targets
    "claude-opus-5": (5.00, 6.25, 10.00, 0.50, 25.00),
    "claude-opus-4-8": (5.00, 6.25, 10.00, 0.50, 25.00),
    "claude-sonnet-5": (2.00, 2.50, 4.00, 0.20, 10.00),
}
# Claude Haiku 5.5 bills a request whose prompt (every input category) is over
# 100,000 tokens at a second rate card.
LONG_PROMPT_PRICES: dict[str, tuple[int, tuple[float, float, float, float, float]]] = {
    "claude-haiku-5-5": (100_000, (0.50, 0.625, 1.00, 0.05, 2.50)),
}
_HIGHEST = (10.00, 12.50, 20.00, 1.00, 50.00)
# No server-side refusal fallback: `fallbacks="default"` does nothing there and a list is a 400.
NO_SERVER_FALLBACK = ("claude-haiku-",)

SYSTEM = """You read month-end variance commentary written by a finance team or an AI copilot, \
and you extract the claims it makes about how expense accounts moved. You do not judge whether \
any claim is true; a separate deterministic system checks every claim against the ledger.

For every sentence that asserts how an account moved between periods, return one claim:
- quote: the sentence, copied exactly, character for character.
- account: the name of the account the sentence is about, chosen from the provided chart of \
accounts, or "" if none fits. Use "Total operating expenses" for claims about total spend.
- direction: "up", "down", or "" if the sentence does not say.
- change_text: the exact substring stating the amount of the change (for example "$90K"), or "".
- percent_text: the exact substring stating a percentage change (for example "16%"), or "".
- prior_text / current_text: exact substrings stating the prior or current balance, or "".
- reason_text: the exact substring stating the cause (for example "our Series B funding round"), \
or "" if no cause is given.
- search_terms: 3 to 8 words or short phrases a bookkeeper would likely have typed in the vendor \
name or memo line of the transactions this particular cause produced: what the event, project or \
purchase is usually called, and the documents or services it involves. Memo lines rarely repeat a \
whole phrase, so give the key single words as well as phrases (for "the warehouse relocation": \
"relocation", "movers", "warehouse move", "freight"). The terms must tell this cause's \
transactions apart from the account's routine, recurring spending: never the account's own name \
or aliases, and never what the account buys every month anyway (for a travel account not \
"travel", "flights" or "hotel"; for a hosting account not "hosting", "cloud" or "compute"). Empty \
if there is no reason.

Copy every substring exactly as written. Do not invent claims, figures or reasons."""

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "quote": {"type": "string"},
                    "account": {"type": "string"},
                    "direction": {"type": "string", "enum": ["up", "down", ""]},
                    "change_text": {"type": "string"},
                    "percent_text": {"type": "string"},
                    "prior_text": {"type": "string"},
                    "current_text": {"type": "string"},
                    "reason_text": {"type": "string"},
                    "search_terms": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["quote", "account", "direction", "change_text", "percent_text",
                             "prior_text", "current_text", "reason_text", "search_terms"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["claims"],
    "additionalProperties": False,
}


class NetworkDisabled(RuntimeError):
    """The model extractor was asked to run in a process where the network is off."""


def payload(text: str, ledger: Ledger) -> str:
    """Exactly what is sent: the explanation and the chart of accounts. Nothing else."""
    return json.dumps({
        "explanation": text,
        "chart_of_accounts": [{"name": a.name, "aliases": list(a.aliases)} for a in ledger.accounts]
        + [{"name": "Total operating expenses", "aliases": ["opex", "total spend"]}],
    }, ensure_ascii=False)


def _default_client():
    import anthropic  # lazy: the package must run without any third-party dependency
    return anthropic.Anthropic()


def _get(obj: Any, name: str) -> Any:
    if obj is None:
        return None
    return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)


def _int(obj: Any, name: str) -> int:
    try:
        return int(_get(obj, name) or 0)
    except (TypeError, ValueError):
        return 0


def usage_breakdown(usage: Any) -> dict[str, int]:
    """Token counts by billing category, from a top-level usage or one iteration entry."""
    creation = _get(usage, "cache_creation")
    write_5m = _int(creation, "ephemeral_5m_input_tokens")
    write_1h = _int(creation, "ephemeral_1h_input_tokens")
    written = _int(usage, "cache_creation_input_tokens")
    if written > write_5m + write_1h:        # no TTL breakdown: price the rest as 5-minute writes
        write_5m = written - write_1h
    return {
        "input_tokens": _int(usage, "input_tokens"),
        "cache_write_5m_tokens": write_5m,
        "cache_write_1h_tokens": write_1h,
        "cache_read_tokens": _int(usage, "cache_read_input_tokens"),
        "output_tokens": _int(usage, "output_tokens"),
        "thinking_tokens": _int(_get(usage, "output_tokens_details"), "thinking_tokens"),
    }


def price(model: str, tokens: dict[str, int]) -> float:
    """USD for one attempt's token counts at `model`'s rates."""
    rates = PRICES.get(model, _HIGHEST)
    prompt = (tokens["input_tokens"] + tokens["cache_write_5m_tokens"]
              + tokens["cache_write_1h_tokens"] + tokens["cache_read_tokens"])
    if model in LONG_PROMPT_PRICES and prompt > LONG_PROMPT_PRICES[model][0]:
        rates = LONG_PROMPT_PRICES[model][1]
    base, write_5m, write_1h, read, out = rates
    return (tokens["input_tokens"] * base + tokens["cache_write_5m_tokens"] * write_5m
            + tokens["cache_write_1h_tokens"] * write_1h + tokens["cache_read_tokens"] * read
            + tokens["output_tokens"] * out) / 1_000_000


def cost(model: str, usage: Any) -> tuple[dict[str, int], float, list[dict]]:
    """(token counts summed over attempts, USD, one entry per attempt).

    When a server-side fallback ran, the top-level usage covers only the attempt
    that produced the message; `usage.iterations` is the per-attempt record, so
    it is summed instead, each attempt at the rates of the model that ran it.
    """
    attempts: list[dict] = []
    iterations = list(_get(usage, "iterations") or [])
    if any(_get(entry, "type") == "fallback_message" for entry in iterations):
        for entry in iterations:
            entry_model = str(_get(entry, "model") or model)
            tokens = usage_breakdown(entry)
            attempts.append({"type": str(_get(entry, "type")), "model": entry_model,
                             "usd": price(entry_model, tokens), **tokens})
    else:
        tokens = usage_breakdown(usage)
        attempts.append({"type": "message", "model": model, "usd": price(model, tokens), **tokens})
    total = {key: sum(a[key] for a in attempts) for key in attempts[0] if key.endswith("_tokens")}
    return total, sum(a["usd"] for a in attempts), attempts


_WORD = re.compile(r"[a-z0-9&]+")


def restates_account(term: str, account: str, ledger: Ledger) -> bool:
    """A term made only of words from the account's own name and aliases ("hosting",
    "cloud costs") matches the account's routine spending, not a cause, so the
    extractor drops it before proposing."""
    entry = next((a for a in ledger.accounts if a.name == account), None)
    if entry is None:
        return False
    vocabulary = {w for phrase in (entry.name, *entry.aliases) for w in _WORD.findall(phrase.lower())}
    words = _WORD.findall(term.lower())
    return bool(words) and all(w in vocabulary or w.rstrip("s") in vocabulary for w in words)


def request_params(model: str, content: str, effort: str = EFFORT,
                   max_tokens: int = MAX_TOKENS) -> dict[str, Any]:
    """The keyword arguments for `client.beta.messages.create`."""
    params: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "system": SYSTEM,
        "output_config": {"effort": effort,
                          "format": {"type": "json_schema", "schema": SCHEMA}},
        "messages": [{"role": "user", "content": content}],
    }
    if not model.startswith(NO_SERVER_FALLBACK):
        params["betas"] = [FALLBACK_BETA]
        params["fallbacks"] = "default"
    return params


class ClaudeExtractor:
    """Proposes claims with Claude; `admit()` and the checks decide everything else.

    Pass `client` to inject a fake in tests. Every request is recorded in
    `transmissions`, which the run report carries.
    """
    name = NAME
    version = VERSION

    def __init__(self, client: Any | None = None, model: str = MODEL,
                 budget: Budget | None = None, effort: str = EFFORT,
                 max_tokens: int = MAX_TOKENS):
        self._client = client
        self.model = model
        self.budget = budget
        self.effort = effort
        self.max_tokens = max_tokens
        self.transmissions: list[dict] = []
        self._lock = threading.Lock()

    @property
    def fingerprint(self) -> str:
        """Changes whenever the prompt, the schema or the request settings do, so
        cached proposals are not reused across them."""
        settings = json.dumps({"effort": self.effort, "max_tokens": self.max_tokens}, sort_keys=True)
        material = SYSTEM + json.dumps(SCHEMA, sort_keys=True) + settings
        return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]

    def propose(self, text: str, ledger: Ledger) -> list[ClaimProposal]:
        if not netguard.network_allowed():
            raise NetworkDisabled(
                "the Claude extractor sends the explanation text off this machine; start the "
                "server with --allow-network to permit it, or use the offline rules extractor")
        if self.budget is not None:
            self.budget.check()       # raises before anything is sent
        content = payload(text, ledger)
        with self._lock:
            if self._client is None:
                self._client = _default_client()
            client = self._client
        response = client.beta.messages.create(
            **request_params(self.model, content, self.effort, self.max_tokens))
        record: dict[str, Any] = {
            "provider": "anthropic", "model": self.model,
            "served_by": str(getattr(response, "model", None) or self.model),
            "effort": self.effort,
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "bytes": len(content.encode("utf-8")) + len(SYSTEM.encode("utf-8")),
            "payload_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "sent": ["explanation text", "chart of accounts (names and aliases)"],
            "not_sent": ["transactions", "vendors", "memos", "amounts", "balances"],
            "stop_reason": getattr(response, "stop_reason", None),
        }
        tokens, usd, attempts = cost(self.model, getattr(response, "usage", None))
        record.update(tokens)
        record["usd"] = round(usd, 6)
        if len(attempts) > 1:
            record["attempts"] = attempts
        if self.budget is not None:
            self.budget.add(tokens["input_tokens"] + tokens["cache_write_5m_tokens"]
                            + tokens["cache_write_1h_tokens"] + tokens["cache_read_tokens"],
                            tokens["output_tokens"], usd)
        with self._lock:
            self.transmissions.append(record)
        if record["stop_reason"] == "refusal":
            record["refusal_category"] = _get(getattr(response, "stop_details", None), "category")
            return []
        if record["stop_reason"] == "max_tokens":
            record["error"] = f"reply cut off at max_tokens={self.max_tokens}"
            return []
        text_block = next((b.text for b in response.content if getattr(b, "type", "") == "text"), "")
        try:
            data = json.loads(text_block)
        except json.JSONDecodeError:
            record["error"] = "response was not valid JSON"
            return []
        proposals = []
        for item in data.get("claims", []):
            terms = [str(t) for t in item.get("search_terms", [])]
            kept = [t for t in terms if not restates_account(t, item.get("account") or "", ledger)]
            if len(kept) < len(terms):
                record.setdefault("dropped_terms", []).extend(sorted(set(terms) - set(kept)))
            item["search_terms"] = kept
            proposals.append(ClaimProposal(
                quote=str(item.get("quote", "")),
                account=item.get("account") or None,
                change_text=item.get("change_text") or None,
                percent_text=item.get("percent_text") or None,
                prior_text=item.get("prior_text") or None,
                current_text=item.get("current_text") or None,
                driver_text=item.get("reason_text") or None,
                driver_terms=tuple(item["search_terms"]),
                direction=item.get("direction") or None,
                extractor=NAME,
            ))
        return proposals
