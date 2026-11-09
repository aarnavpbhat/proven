"""An extractor backed by an open-weight model behind any OpenAI-compatible endpoint.

It is the same contract as the Claude extractor (`proven/llm.py`): the same system
prompt, the same JSON schema, the same payload (explanation text and chart of
accounts, nothing from the ledger), and the same output, a list of `ClaimProposal`s
that `claims.admit()` then grants or refuses. The model proposes; it never decides.

WHY IT EXISTS

The promise is "nothing leaves this machine". With a model served on loopback
(Ollama's default is http://127.0.0.1:11434/v1) the promise holds: the network
guard allows loopback, so this extractor runs without `--allow-network`. If the
configured host is anywhere else the extractor refuses unless the process was
started with the network explicitly allowed, exactly as the Claude one does.

CONFIGURATION (environment)

    PROVEN_OPENAI_BASE_URL   default http://127.0.0.1:11434/v1
    PROVEN_OPENAI_API_KEY    optional bearer token
    PROVEN_OPENAI_MODEL      model id when none is passed on the command line
    PROVEN_OPENAI_REASONING  `reasoning_effort` sent to a loopback server
                             (default "none": thinking models answer directly;
                             set it to "" to send nothing)
    PROVEN_OPENAI_TIMEOUT    seconds per request, default 300

STRUCTURED OUTPUT

The request carries `response_format: {"type": "json_schema", ...}` with the
shared schema. Ollama compiles that into a grammar, so the reply is constrained
to the schema. A server that rejects it (HTTP 400/422) is retried once with
`{"type": "json_object"}`, and whatever comes back is validated here regardless:
`<think>` blocks are stripped, the first JSON object is extracted, and anything
that is not the expected shape yields no proposals and an `error` on the
transmission record. A bad reply never raises.

Standard library only (`urllib.request`).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import urlparse

from proven import netguard
from proven.budget import Budget
from proven.claims import ClaimProposal
from proven.ledger import Ledger
from proven.llm import SCHEMA, SYSTEM, NetworkDisabled, payload

NAME = "openweight"
VERSION = "0.1"
DEFAULT_BASE_URL = "http://127.0.0.1:11434/v1"

#: (url, headers, body) -> response bytes. Raises urllib.error.HTTPError on a non-2xx status.
Transport = Callable[[str, dict[str, str], bytes], bytes]

_THINK = re.compile(r"<think(?:ing)?>.*?</think(?:ing)?>", re.DOTALL | re.IGNORECASE)
_THINK_OPEN = re.compile(r"<think(?:ing)?>.*\Z", re.DOTALL | re.IGNORECASE)
_LOOPBACK_NAMES = {"localhost", "::1", "0.0.0.0", ""}


def is_loopback(host: str) -> bool:
    host = (host or "").strip("[]").lower()
    return host in _LOOPBACK_NAMES or host.startswith("127.")


def strip_thinking(text: str) -> str:
    """Remove `<think>` blocks, including one that was never closed."""
    text = _THINK.sub("", text or "")
    text = _THINK_OPEN.sub("", text)
    text = re.sub(r"</think(?:ing)?>", "", text, flags=re.IGNORECASE)
    return text.strip()


def parse_reply(content: str) -> dict[str, Any]:
    """The first JSON object in the reply, after thinking and code fences are removed.

    Raises ValueError if there is none or it lacks a `claims` list."""
    text = strip_thinking(content)
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()
    data: Any = None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                data = None
    if not isinstance(data, dict) or not isinstance(data.get("claims"), list):
        raise ValueError("reply was not a JSON object with a claims list")
    return data


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def proposals_from(data: dict[str, Any]) -> list[ClaimProposal]:
    proposals = []
    for item in data["claims"]:
        if not isinstance(item, dict) or not _text(item.get("quote")).strip():
            continue
        terms = item.get("search_terms")
        direction = _text(item.get("direction"))
        proposals.append(ClaimProposal(
            quote=_text(item.get("quote")),
            account=_text(item.get("account")) or None,
            change_text=_text(item.get("change_text")) or None,
            percent_text=_text(item.get("percent_text")) or None,
            prior_text=_text(item.get("prior_text")) or None,
            current_text=_text(item.get("current_text")) or None,
            driver_text=_text(item.get("reason_text")) or None,
            driver_terms=tuple(t for t in terms if isinstance(t, str)) if isinstance(terms, list) else (),
            direction=direction if direction in ("up", "down") else None,
            extractor=NAME,
        ))
    return proposals


def _urllib_transport(timeout: float, direct: bool) -> Transport:
    def send(url: str, headers: dict[str, str], body: bytes) -> bytes:
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        # A loopback call must not be diverted through an HTTP proxy from the environment.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({})) if direct \
            else urllib.request.build_opener()
        with opener.open(request, timeout=timeout) as response:
            return response.read()
    return send


class OpenWeightExtractor:
    name = NAME
    version = VERSION

    def __init__(self, transport: Transport | None = None, model: str | None = None,
                 base_url: str | None = None, api_key: str | None = None,
                 budget: Budget | None = None, timeout: float | None = None,
                 reasoning_effort: str | None = None):
        self.base_url = (base_url or os.environ.get("PROVEN_OPENAI_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.model = model or os.environ.get("PROVEN_OPENAI_MODEL") or ""
        self.api_key = api_key if api_key is not None else os.environ.get("PROVEN_OPENAI_API_KEY", "")
        self.host = urlparse(self.base_url).hostname or ""
        self.loopback = is_loopback(self.host)
        self.budget = budget
        if reasoning_effort is None:
            reasoning_effort = os.environ.get("PROVEN_OPENAI_REASONING", "none")
        self.reasoning_effort = reasoning_effort
        if timeout is None:
            timeout = float(os.environ.get("PROVEN_OPENAI_TIMEOUT") or 300)
        self._transport = transport or _urllib_transport(timeout, self.loopback)
        self.transmissions: list[dict] = []

    @property
    def fingerprint(self) -> str:
        """Changes whenever the prompt, schema or request settings do."""
        material = SYSTEM + json.dumps(SCHEMA, sort_keys=True) + f"|{self.reasoning_effort}|t0"
        return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]

    def _body(self, content: str, response_format: dict[str, Any]) -> bytes:
        body: dict[str, Any] = {
            "model": self.model,
            "temperature": 0,
            "messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": content}],
            "response_format": response_format,
        }
        if self.loopback and self.reasoning_effort:
            body["reasoning_effort"] = self.reasoning_effort
        return json.dumps(body, ensure_ascii=False).encode("utf-8")

    def propose(self, text: str, ledger: Ledger) -> list[ClaimProposal]:
        if not self.loopback and not netguard.network_allowed():
            raise NetworkDisabled(
                f"the open-weight extractor is pointed at {self.host!r}, which is not this machine; "
                "start with --allow-network to permit sending the explanation text there, or use "
                "a loopback server (the default is http://127.0.0.1:11434/v1)")
        if not self.model:
            raise ValueError("no model: pass --model or set PROVEN_OPENAI_MODEL")
        if self.budget is not None:
            self.budget.check()
        content = payload(text, ledger)
        schema_format = {"type": "json_schema",
                         "json_schema": {"name": "claims", "strict": True, "schema": SCHEMA}}
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        record: dict[str, Any] = {
            "provider": "openai-compatible", "model": self.model, "host": self.host,
            "loopback": self.loopback,
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "bytes": len(content.encode("utf-8")) + len(SYSTEM.encode("utf-8")),
            "payload_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "sent": ["explanation text", "chart of accounts (names and aliases)"],
            "not_sent": ["transactions", "vendors", "memos", "amounts", "balances"],
            "response_format": "json_schema",
        }
        self.transmissions.append(record)
        url = f"{self.base_url}/chat/completions"
        try:
            try:
                raw = self._transport(url, headers, self._body(content, schema_format))
            except urllib.error.HTTPError as exc:
                if exc.code not in (400, 422):
                    raise
                record["response_format"] = "json_object"
                raw = self._transport(url, headers, self._body(content, {"type": "json_object"}))
            reply = json.loads(raw)
            choice = reply["choices"][0]
            message = choice["message"]
            record["finish_reason"] = choice.get("finish_reason")
        except netguard.NetworkBlocked:
            raise
        except (urllib.error.URLError, OSError, ValueError, KeyError, IndexError, TypeError) as exc:
            record["error"] = f"request failed: {type(exc).__name__}: {exc}"
            return []
        usage = reply.get("usage") if isinstance(reply, dict) else None
        usage = usage if isinstance(usage, dict) else {}
        record["input_tokens"] = int(usage.get("prompt_tokens") or 0)
        record["output_tokens"] = int(usage.get("completion_tokens") or 0)
        if self.budget is not None:
            self.budget.add(record["input_tokens"], record["output_tokens"])
        try:
            return proposals_from(parse_reply(_text(message.get("content") if isinstance(message, dict) else "")))
        except ValueError as exc:
            record["error"] = str(exc)
            return []
