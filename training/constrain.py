"""Constrained decoding for the proposer: replies that are admissible by construction.

The proposer answers with one JSON object (`proven.llm.SCHEMA`). Three of its promises can
be checked against the request alone, so they are enforced while the reply is generated
instead of hoped for:

  * the reply is the schema's JSON, in the layout the model was trained on;
  * `quote`, `change_text`, `percent_text`, `prior_text`, `current_text` and `reason_text`
    are copied from the explanation, byte for byte (a substring of it, or empty);
  * `account` is a name from the chart of accounts sent with the request, or empty.

`search_terms` stay free text. They are the model's guess at ledger wording it is never
shown (`proven.llm.payload` sends no transactions, vendors or memos), so there is nothing
on the model's side of that boundary to copy them from, and this module does not look at
the ledger either.

HOW

`Grammar` is a small automaton over the BYTES of the reply. A token is allowed when feeding
its bytes to the automaton never rejects; the allowed set is found by walking the
vocabulary's byte trie in step with the automaton, so a token that spans several pieces of
the layout (Qwen's vocabulary has `", "`, ` [{"` and `"]}`) needs no special case. Inside a
copied field the automaton's state is the set of positions in the explanation the text so
far could end at; a byte is allowed if it follows at one of them. The mask is added to the
logits before sampling, so it works the same for greedy decoding and for sampling at any
temperature.

The idea of masking logits so that only spans of the input can be produced follows
"Strategies for Span Labeling with Large Language Models" (LogitMatch, arXiv 2601.16946)
and the copy-constrained decoding line of work; the schema half is ordinary grammar-
constrained decoding. An explanation or account name containing a double quote or a
backslash would need JSON escapes inside the copied text; `Grammar.supported` is False for
those and the caller decodes them unconstrained.
"""
from __future__ import annotations

import json
from typing import Iterable, Sequence

MAX_CLAIMS = 16
MAX_TERMS = 8
MAX_TERM_BYTES = 64
TOTAL = "Total operating expenses"

QUOTE, BACKSLASH = 0x22, 0x5C
COPIED = ("quote", "change_text", "percent_text", "prior_text", "current_text", "reason_text")
FIELDS = ("quote", "account", "direction", "change_text", "percent_text", "prior_text",
          "current_text", "reason_text")
END = ("END",)


def bytes_to_unicode() -> dict[int, str]:
    """GPT-2's byte-to-character table, which byte-level BPE vocabularies are written in."""
    bs = list(range(ord("!"), ord("~") + 1)) + list(range(0xA1, 0xAD)) + list(range(0xAE, 0x100))
    cs, n = bs[:], 0
    for b in range(256):
        if b not in bs:
            bs.append(b)
            cs.append(256 + n)
            n += 1
    return {b: chr(c) for b, c in zip(bs, cs)}


def token_bytes(tokenizer) -> list[bytes | None]:
    """Every ordinary token's bytes, by id; None for special and added tokens."""
    decode = {c: b for b, c in bytes_to_unicode().items()}
    special = set(tokenizer.all_special_ids) | set(tokenizer.get_added_vocab().values())
    out: list[bytes | None] = []
    for token_id, text in enumerate(tokenizer.convert_ids_to_tokens(list(range(len(tokenizer))))):
        if token_id in special or text is None or any(ch not in decode for ch in text):
            out.append(None)
        else:
            out.append(bytes(decode[ch] for ch in text))
    return out


class Vocab:
    """The vocabulary as a byte trie, plus what does not depend on the request."""

    def __init__(self, tokens: Sequence[bytes | None], eos: int):
        self.size = len(tokens)
        self.eos = eos
        self.tokens = tokens
        self.root: list = [{}, -1]                       # [children by byte, token id or -1]
        self.plain: list[int] = []                       # tokens that fit inside any free string
        self.quoted: list[int] = []                      # tokens containing a double quote
        for token_id, raw in enumerate(tokens):
            if not raw:
                continue
            node = self.root
            for b in raw:
                node = node[0].setdefault(b, [{}, -1])
            node[1] = token_id
            if any(b < 0x20 or b == BACKSLASH for b in raw):
                continue
            (self.quoted if QUOTE in raw else self.plain).append(token_id)


class Grammar:
    """The reply automaton for one request. States are small hashable tuples."""

    def __init__(self, explanation: str, accounts: Iterable[str],
                 max_claims: int = MAX_CLAIMS, max_terms: int = MAX_TERMS):
        self.text = explanation.encode("utf-8")
        names = [n for n in dict.fromkeys(list(accounts) + [TOTAL]) if n]
        self.supported = not any('"' in s or "\\" in s for s in [explanation, *names])
        self.options = {
            "account": tuple(n.encode("utf-8") for n in names) + (b"",),
            "direction": (b"up", b"down", b""),
        }
        self.max_claims, self.max_terms = max_claims, max_terms
        self.where: dict[int, frozenset[int]] = {}       # byte -> positions just after it
        index: dict[int, set[int]] = {}
        for i, b in enumerate(self.text):
            if b > 0x20 and b & 0xC0 != 0x80:             # a copy starts on a whole, visible character
                index.setdefault(b, set()).add(i + 1)
        self.where = {b: frozenset(p) for b, p in index.items()}
        self.start = self._alt(((b'{"claims": [{"quote": "', ("V", 0, 0)),
                                (b'{"claims": []}', END)))

    # -- building states ---------------------------------------------------------------

    def _alt(self, alts: tuple) -> tuple:
        for rest, target in alts:
            if not rest:
                return self._enter(target)
        return ("A", alts)

    def _enter(self, target: tuple) -> tuple:
        kind = target[0]
        if kind == "V":                                   # the value of field k of claim c
            _, k, c = target
            name = FIELDS[k]
            if name in COPIED:
                return ("S", None, k, c)
            return ("E", self.options[name], k, c)
        if kind == "T":                                   # a search term
            return ("T", 0, target[1], target[2])
        if kind == "X":                                   # the terms list of claim c is closed
            return self._after_claim(target[1])
        return target

    def _after_value(self, k: int, c: int) -> tuple:
        """The closing quote of field k has been read."""
        if k + 1 < len(FIELDS):
            return self._alt(((b', "' + FIELDS[k + 1].encode() + b'": "', ("V", k + 1, c)),))
        return self._alt(((b', "search_terms": ["', ("T", c, 0)),
                          (b', "search_terms": []', ("X", c))))

    def _after_claim(self, c: int) -> tuple:
        alts = [(b"}]}", END)]
        if c + 1 < self.max_claims:
            alts.append((b'}, {"quote": "', ("V", 0, c + 1)))
        return self._alt(tuple(alts))

    # -- one byte ----------------------------------------------------------------------

    def step(self, state: tuple, b: int):
        kind = state[0]
        if kind == "A":
            alts = tuple((rest[1:], target) for rest, target in state[1] if rest[0] == b)
            return self._alt(alts) if alts else None
        if kind == "S":
            _, positions, k, c = state
            if b == QUOTE:
                if positions is None and FIELDS[k] == "quote":
                    return None                           # a claim must quote something
                if positions is not None and not any(
                        p == len(self.text) or self.text[p] & 0xC0 != 0x80 for p in positions):
                    return None                           # not in the middle of a character
                return self._after_value(k, c)
            if b < 0x20:
                return None                               # a copy stays on one line
            if positions is None:
                nxt = self.where.get(b)
            else:
                nxt = frozenset(p + 1 for p in positions if p < len(self.text) and self.text[p] == b)
            return ("S", nxt, k, c) if nxt else None
        if kind == "E":
            _, options, k, c = state
            if b == QUOTE:
                return self._after_value(k, c) if b"" in options else None
            left = tuple(o[1:] for o in options if o and o[0] == b)
            return ("E", left, k, c) if left else None
        if kind == "T":
            _, length, c, t = state
            if b == QUOTE:
                if not length:
                    return None
                alts = [(b"]", ("X", c))]
                if t + 1 < self.max_terms:
                    alts.append((b', "', ("T", c, t + 1)))
                return self._alt(tuple(alts))
            if b < 0x20 or b == BACKSLASH or length >= MAX_TERM_BYTES:
                return None
            return ("T", length + 1, c, t)
        return None                                      # END takes no more bytes

    def feed(self, state: tuple, data: bytes):
        for b in data:
            state = self.step(state, b)
            if state is None:
                return None
        return state

    def accepts(self, reply: str) -> bool:
        return self.feed(self.start, reply.encode("utf-8")) == END


class Mask:
    """Allowed token ids per automaton state, for one request."""

    def __init__(self, vocab: Vocab, grammar: Grammar):
        self.vocab, self.grammar = vocab, grammar
        self._memo: dict[tuple, list[int]] = {}

    def allowed(self, state: tuple) -> list[int]:
        if state == END:
            return [self.vocab.eos]
        key = state
        if state[0] == "T":                               # only "empty / open / full" matters
            length = state[1]
            key = ("T", 0 if not length else (MAX_TERM_BYTES if length >= MAX_TERM_BYTES else 1),
                   state[2], state[3])
        elif state[0] == "S" and state[1] is not None:
            key = None                                    # position sets rarely repeat
        if key is not None and key in self._memo:
            return self._memo[key]
        out = self._free(key) if state[0] == "T" else self._walk(state)
        if key is not None:
            self._memo[key] = out
        return out

    def _walk(self, state: tuple) -> list[int]:
        out, step = [], self.grammar.step
        stack = [(self.vocab.root, state)]
        while stack:
            node, at = stack.pop()
            for b, child in node[0].items():
                nxt = step(at, b)
                if nxt is None:
                    continue
                if child[1] >= 0:
                    out.append(child[1])
                if child[0] and nxt != END:
                    stack.append((child, nxt))
        return out

    def _free(self, state: tuple) -> list[int]:
        """Inside a search term almost every token fits; only the ones with a quote need a look."""
        feed, tokens = self.grammar.feed, self.vocab.tokens
        out = [] if state[1] >= MAX_TERM_BYTES else list(self.vocab.plain)
        out += [t for t in self.vocab.quoted if feed(state, tokens[t]) is not None]
        return out


class Constraint:
    """A logits processor for one row of a batch (`mlx_lm` calls it once per generated token).

    It is called with the tokens so far and the next-token logits. The first call is before
    any reply token; on each later call the last token of the context is the one just
    generated. `broken` is set, and masking stops, if a token ever falls outside the grammar
    (which the mask makes impossible unless the caller skips a call).
    """

    def __init__(self, vocab: Vocab, explanation: str, accounts: Iterable[str]):
        import numpy as np
        self._np = np
        self.vocab = vocab
        self.grammar = Grammar(explanation, accounts)
        self.mask = Mask(vocab, self.grammar)
        self.state = self.grammar.start
        self.calls = 0
        self.broken = False

    def advance(self, token_id: int) -> None:
        raw = self.vocab.tokens[token_id] if 0 <= token_id < self.vocab.size else None
        if self.state == END and token_id == self.vocab.eos:
            return
        nxt = self.grammar.feed(self.state, raw) if raw else None
        if nxt is None:
            self.broken = True
        else:
            self.state = nxt

    def __call__(self, context, logits):
        import mlx.core as mx
        if self.calls:
            self.advance(int(context[-1].item()))
        self.calls += 1
        if self.broken:
            return logits
        bias = self._np.full((self.vocab.size,), -1e9, dtype=self._np.float32)
        bias[self.mask.allowed(self.state)] = 0.0
        width = logits.shape[-1]
        if width != self.vocab.size:                      # padded embedding rows: never allowed
            full = self._np.full((width,), -1e9, dtype=self._np.float32)
            full[:min(width, self.vocab.size)] = bias[:width]
            bias = full
        return logits + mx.array(bias)[None].astype(logits.dtype)


def accounts_of(content: str) -> tuple[str, list[str]]:
    """The explanation and the chart's account names, from a request payload."""
    data = json.loads(content)
    return data["explanation"], [a["name"] for a in data["chart_of_accounts"]]
