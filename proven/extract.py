"""The default extractor: deterministic, offline, and honest about what it misses.

It proposes at most one claim per sentence, reading the forms variance
commentary is actually written in:

    Legal costs rose $90K because of our funding round.
    Cloud hosting increased approximately 18% to $96.4K, driven by higher AWS usage.
    The $45K increase in recruiting fees was primarily due to the VP Engineering search.

A sentence that states a figure but yields no claim is not dropped: it is
returned as *unextracted*, and the report counts it. Coverage is a number this
product publishes, not a gap it hopes nobody computes.

`extractor="rules"` proposals go through exactly the same `admit()` as a
language model's, so the boundary is exercised on every run — not only when a
model is switched on.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from proven.claims import ClaimProposal, has_figures, read_sentence
from proven.ledger import Ledger

NAME = "rules"
VERSION = "0.1"


@dataclass(frozen=True)
class Sentence:
    """A sentence of the explanation, with its character offsets."""
    start: int
    end: int
    text: str


_BOUNDARY = re.compile(r"(?<=[.!?])\s+|\n+")
_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")


def sentences(text: str) -> list[Sentence]:
    """Sentences with offsets into `text`. A decimal point is never a boundary."""
    out: list[Sentence] = []
    position = 0
    for match in list(_BOUNDARY.finditer(text)) + [None]:
        end = match.start() if match else len(text)
        chunk = text[position:end]
        bullet = _BULLET.match(chunk)
        lead = bullet.end() if bullet else len(chunk) - len(chunk.lstrip())
        body = chunk[lead:].rstrip()
        if body:
            out.append(Sentence(position + lead, position + lead + len(body), body))
        position = match.end() if match else len(text)
    return out


class RuleExtractor:
    """The default, offline extractor: at most one proposal per sentence, read by rule."""
    name = NAME
    version = VERSION

    def propose(self, text: str, ledger: Ledger) -> list[ClaimProposal]:
        proposals: list[ClaimProposal] = []
        for sentence in sentences(text):
            reading = read_sentence(sentence.text, ledger)
            figure_stated = any((reading.change, reading.percent, reading.prior, reading.current))
            if not figure_stated and not (reading.account and reading.direction):
                continue
            if not (reading.account or reading.direction):
                continue
            proposals.append(ClaimProposal(
                quote=sentence.text,
                account=reading.account,
                change_text=reading.change.text if reading.change else None,
                percent_text=reading.percent.text if reading.percent else None,
                prior_text=reading.prior.text if reading.prior else None,
                current_text=reading.current.text if reading.current else None,
                driver_text=reading.driver,
                extractor=NAME,
            ))
        return proposals


def unextracted(text: str, claimed_spans: list[tuple[int, int]]) -> list[Sentence]:
    """Sentences that state a figure and produced no admitted claim."""
    out = []
    for sentence in sentences(text):
        covered = any(s < sentence.end and sentence.start < e for s, e in claimed_spans)
        if not covered and has_figures(sentence.text):
            out.append(sentence)
    return out
