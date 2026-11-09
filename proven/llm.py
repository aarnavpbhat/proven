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

Requests use `claude-opus-5-5` with structured output, and opt into the API's
server-side fallback (`fallbacks="default"`) so that a classifier refusal is
retried on Anthropic's recommended fallback model instead of returning nothing.
A refusal that survives the fallback produces no proposals and is recorded.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from proven import netguard
from proven.budget import Budget
from proven.claims import ClaimProposal
from proven.ledger import Ledger

NAME = "claude"
VERSION = "0.1"
MODEL = "claude-opus-5-5"

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
- search_terms: 3 to 8 short words or phrases likely to appear in the vendor names or memo lines \
of transactions caused by that reason (synonyms, document types, vendor categories). Empty if \
there is no reason.

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


class ClaudeExtractor:
    name = NAME
    version = VERSION

    def __init__(self, client: Any | None = None, model: str = MODEL,
                 budget: Budget | None = None):
        self._client = client
        self.model = model
        self.budget = budget
        self.transmissions: list[dict] = []

    @property
    def fingerprint(self) -> str:
        """Changes whenever the prompt or schema does, so cached proposals are not reused."""
        material = SYSTEM + json.dumps(SCHEMA, sort_keys=True)
        return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]

    def propose(self, text: str, ledger: Ledger) -> list[ClaimProposal]:
        if not netguard.network_allowed():
            raise NetworkDisabled(
                "the Claude extractor sends the explanation text off this machine; start the "
                "server with --allow-network to permit it, or use the offline rules extractor")
        if self.budget is not None:
            self.budget.check()       # raises before anything is sent
        content = payload(text, ledger)
        if self._client is None:
            self._client = _default_client()
        client = self._client
        response = client.beta.messages.create(
            model=self.model,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=SYSTEM,
            output_config={"effort": "medium",
                           "format": {"type": "json_schema", "schema": SCHEMA}},
            messages=[{"role": "user", "content": content}],
        )
        record = {
            "provider": "anthropic", "model": self.model,
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "bytes": len(content.encode("utf-8")) + len(SYSTEM.encode("utf-8")),
            "payload_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "sent": ["explanation text", "chart of accounts (names and aliases)"],
            "not_sent": ["transactions", "vendors", "memos", "amounts", "balances"],
            "stop_reason": getattr(response, "stop_reason", None),
        }
        usage = getattr(response, "usage", None)
        record["input_tokens"] = int(getattr(usage, "input_tokens", 0) or 0)
        record["output_tokens"] = int(getattr(usage, "output_tokens", 0) or 0)
        if self.budget is not None:
            self.budget.add(record["input_tokens"], record["output_tokens"])
        self.transmissions.append(record)
        if record["stop_reason"] == "refusal":
            return []
        text_block = next((b.text for b in response.content if getattr(b, "type", "") == "text"), "")
        try:
            data = json.loads(text_block)
        except json.JSONDecodeError:
            record["error"] = "response was not valid JSON"
            return []
        proposals = []
        for item in data.get("claims", []):
            proposals.append(ClaimProposal(
                quote=str(item.get("quote", "")),
                account=item.get("account") or None,
                change_text=item.get("change_text") or None,
                percent_text=item.get("percent_text") or None,
                prior_text=item.get("prior_text") or None,
                current_text=item.get("current_text") or None,
                driver_text=item.get("reason_text") or None,
                driver_terms=tuple(str(t) for t in item.get("search_terms", [])),
                direction=item.get("direction") or None,
                extractor=NAME,
            ))
        return proposals
