"""What an explanation claims, and the boundary a proposed claim must cross.

PROPOSE, THEN ADMIT

An extractor — the rule-based one in `extract.py`, or a language model in
`llm.py` — returns `ClaimProposal`s. A proposal is a request to be checked, not
a fact. `admit()` turns it into a `Claim` using only deterministic reads of the
explanation's own text:

  * the quote must occur verbatim in the explanation, or the proposal is
    rejected — a model inventing a sentence becomes a string search;
  * every stated figure must occur in the quote, or the proposal is rejected;
  * direction ("rose" / "fell") and attribution strength ("primarily", "partly")
    are re-read from the quote, never taken from the proposal;
  * the account is resolved from an alias written in the quote where one
    exists; a mapping only the model supplied is kept but marked, and a claim
    resting on it can never be decided without a person;
  * the stated reason must be a span of the quote, and the search terms derived
    from it are marked by origin: written in the quote, expanded from the
    declared lexicon, or proposed by a model.

`Claim` has no verdict field. A verdict is something `verify.py` computes at a
point in time under a declared policy; it lives on `ClaimResult`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from proven.ledger import TOTAL, TOTAL_ALIASES, Ledger
from proven.money import Figure, find_money, find_percents, parse_money, parse_percent


class Strength(str, Enum):
    """How much of the movement the explanation attributes to its stated reason."""

    FULL = "full"            # "because of", "due to", "driven by"
    MAJORITY = "majority"    # "primarily", "mainly", "largely"
    PARTIAL = "partial"      # "partly", "in part"


# ── Deterministic readers ────────────────────────────────────────────────

_MAJORITY = ("primarily", "mainly", "largely", "mostly", "chiefly", "principally",
             "predominantly", "in large part")
_PARTIAL = ("partly", "partially", "in part")
_HEDGE = r"(?:primarily|mainly|largely|mostly|partly|partially|chiefly|principally|predominantly|in\s+large\s+part|in\s+part)"

_CONNECTOR = re.compile(
    rf"(?:\b(?P<pre>{_HEDGE})\s+)?"
    rf"\b(?P<conn>due\s+(?:(?P<mid1>{_HEDGE})\s+)?to"
    rf"|because(?:\s+of)?"
    rf"|driven\s+(?:(?P<mid2>{_HEDGE})\s+)?by"
    rf"|as\s+a\s+result\s+of"
    rf"|reflecting|attributable\s+to|owing\s+to|thanks\s+to|on\s+the\s+back\s+of"
    rf"|on(?=\s+(?:higher|lower|increased|decreased|additional)\b))\b",
    re.IGNORECASE,
)

_CLAUSE_END = re.compile(
    r"\s*(?:;|\s[—–-]\s|,\s*(?:partially|partly)?\s*offset\b|,\s*which\b|,\s*while\b)",
    re.IGNORECASE,
)

_UP = re.compile(
    r"\b(rose|risen|increased|increase|grew|grown|growth|climbed|jumped|rise|higher|"
    r"(?:was|were|went|is|came\s+in)\s+up)\b", re.IGNORECASE)
_DOWN = re.compile(
    r"\b(fell|fallen|decreased|decrease|declined|decline|dropped|drop|lower|reduction|"
    r"reduced|shrank|(?:was|were|went|is|came\s+in)\s+down)\b", re.IGNORECASE)

_CURRENT_CUE = re.compile(r"\b(?:to|at|reached|totaled|totalled|were|was)\s*$", re.IGNORECASE)
_PRIOR_CUE = re.compile(r"\bfrom\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class Reading:
    """What a sentence says, read without a model."""

    head: str                    # the part before the stated reason
    driver: str | None           # the stated reason, verbatim
    direction: int | None        # +1 rose, -1 fell
    strength: Strength
    account: str | None
    change: Figure | None
    percent: Figure | None
    prior: Figure | None
    current: Figure | None


def split_reason(sentence: str) -> tuple[str, str | None, Strength]:
    """(head, stated reason or None, attribution strength)."""
    match = _CONNECTOR.search(sentence)
    if not match:
        return sentence, None, Strength.FULL
    hedge = (match.group("pre") or match.group("mid1") or match.group("mid2") or "").lower()
    if not hedge:
        window = sentence[max(0, match.start() - 30):match.start()].lower()
        hedge = next((h for h in _PARTIAL + _MAJORITY if re.search(rf"\b{h}\b", window)), "")
    hedge = re.sub(r"\s+", " ", hedge)
    strength = (Strength.PARTIAL if hedge in _PARTIAL
                else Strength.MAJORITY if hedge in _MAJORITY else Strength.FULL)
    rest = sentence[match.end():]
    end = _CLAUSE_END.search(rest)
    driver = (rest[:end.start()] if end else rest).strip().rstrip(".!?,:").strip()
    return sentence[:match.start()], (driver or None), strength


def read_direction(head: str) -> int | None:
    up, down = _UP.search(head), _DOWN.search(head)
    if up and (not down or up.start() < down.start()):
        return 1
    if down:
        return -1
    return None


def resolve_account(head: str, ledger: Ledger) -> str | None:
    """The account an alias in `head` names: earliest, then longest, match."""
    lower = head.lower()
    hits: list[tuple[int, int, str]] = []
    candidates = [(alias, TOTAL) for alias in TOTAL_ALIASES]
    for account in ledger.accounts:
        candidates.append((account.name.lower(), account.name))
        candidates.extend((alias.lower(), account.name) for alias in account.aliases)
    for alias, name in candidates:
        for match in re.finditer(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", lower):
            hits.append((match.start(), -len(alias), name))
    return min(hits)[2] if hits else None


def read_figures(head: str) -> tuple[Figure | None, Figure | None, Figure | None, Figure | None]:
    """(change, percent, prior, current) as stated in the head of a sentence."""
    change = prior = current = None
    for figure in find_money(head):
        before = head[:figure.start]
        if _PRIOR_CUE.search(before) and prior is None:
            prior = figure
        elif _CURRENT_CUE.search(before) and current is None:
            current = figure
        elif change is None:
            change = figure
    percents = find_percents(head)
    return change, (percents[0] if percents else None), prior, current


def read_sentence(sentence: str, ledger: Ledger) -> Reading:
    head, driver, strength = split_reason(sentence)
    change, percent, prior, current = read_figures(head)
    return Reading(head=head, driver=driver, direction=read_direction(head),
                   strength=strength, account=resolve_account(head, ledger),
                   change=change, percent=percent, prior=prior, current=current)


def has_figures(sentence: str) -> bool:
    return bool(find_money(sentence) or find_percents(sentence))


# ── Search terms for a stated reason ─────────────────────────────────────

#: A declared calibration table: how a writer refers to a cause, and the words
#: that cause leaves in a ledger's memo and vendor fields. It is data, it is
#: reviewed like code, and every entry is exercised by a test. Adding to it is
#: the in-product version of Aptio's calibration rule — and like one, an entry
#: that makes sound explanations fail is a regression.
LEXICON: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    # (name, phrases a writer uses, words the cause leaves in vendor/memo fields)
    ("financing", ("funding", "financing", "fundrais", "series a", "series b", "series c",
                   "capital raise", "investor"),
     ("financing", "funding", "fundrais", "series a", "series b", "series c", "investor",
      "term sheet")),
    ("litigation", ("litigation", "lawsuit", "dispute", "settlement", "patent case"),
     ("litigation", "lawsuit", "dispute", "settlement", "deposition", "arbitration")),
    ("conference", ("conference", "trade show", "tradeshow", "summit", "sponsorship", "booth"),
     ("conference", "summit", "sponsorship", "booth", "trade show", "expo")),
    ("campaign", ("campaign", "product launch", "paid search", "paid social"),
     ("campaign", "launch", "paid search", "paid social")),
    ("cloud_usage", ("aws", "compute", "migration", "usage"),
     ("aws", "ec2", "compute", "migration", "usage")),
    ("ml_training", ("model training", "training run", "gpu"),
     ("gpu", "model training")),
    ("renewal", ("renewal", "license", "licence", "subscription renewal"),
     ("renewal", "license", "licence")),
    ("compliance", ("soc 2", "compliance"),
     ("soc 2", "compliance")),
    ("offsite", ("offsite", "off-site", "retreat", "kickoff"),
     ("offsite", "off-site", "retreat", "kickoff")),
    ("office_lease", ("office lease", "new office", "office expansion", "lease"),
     ("lease", "deposit")),
    ("buildout", ("build-out", "buildout", "renovation"),
     ("build-out", "buildout", "renovation")),
    ("design", ("redesign", "website", "designers"),
     ("redesign", "website", "designer")),
    ("contract_engineering", ("contract engineers", "mobile app"),
     ("contract engineer", "mobile app")),
    ("recruiting", ("executive search", "engineering search", "search firm", "placement",
                    "recruiter"),
     ("search", "placement", "recruiter")),
    ("d_and_o", ("d&o", "directors and officers"),
     ("d&o",)),
    ("customer_travel", ("customer visit", "customer travel", "client visit", "sales travel",
                         "roadshow"),
     ("customer visit", "client visit", "sales trip", "roadshow")),
)

#: Every word the lexicon declares as a trace a cause leaves in the ledger.
LEXICON_TERMS = frozenset(term for _name, _triggers, terms in LEXICON for term in terms)

#: Entries a reviewer confirmed, in the same (name, triggers, terms) shape as LEXICON.
#: Empty unless `set_learned()` is called, so the benchmark and the tests never depend
#: on what happens to be on disk.
LEARNED: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = []


def set_learned(entries: list[tuple[str, tuple[str, ...], tuple[str, ...]]]) -> None:
    """Replace the reviewer-confirmed entries. Their terms get the origin "learned"."""
    LEARNED[:] = [(name, tuple(t.lower() for t in triggers), tuple(t.lower() for t in terms))
                  for name, triggers, terms in entries]


def declared_terms() -> frozenset[str]:
    """Every term vouched for by the built-in lexicon or by a reviewer."""
    return LEXICON_TERMS | {term for _name, _triggers, terms in LEARNED for term in terms}


STOPWORDS = frozenset("""
a an and as at by for from in into of on onto or over than that the their these this those
to under with our its we us company team not fewer
higher lower increased decreased increase decrease additional extra more less new
one-time onetime timing absence lack lapping prior last previous period comparison
cost costs fee fees expense expenses spend spending charge charges invoice invoices
payment payments vendor vendors work item items activity activities level levels volume
related associated driven due result because reflecting primarily mainly largely mostly
partly partially month months monthly quarter quarterly year yearly annual
recurring non-recurring nonrecurring ongoing continued continuing several various general
overall total other some certain large larger significant usual normal
january february march april may june july august september october november december
jan feb mar apr jun jul aug sep sept oct nov dec
spring summer fall autumn winter
""".split())

_TOKEN = re.compile(r"[a-z0-9][a-z0-9&'\-]*")


@dataclass(frozen=True)
class Term:
    text: str
    origin: str      # "quote" | "lexicon" | "learned" | "model"

    def to_dict(self) -> dict:
        return {"text": self.text, "origin": self.origin}


def _account_tokens(account: str | None, ledger: Ledger) -> set[str]:
    if account is None or account == TOTAL:
        return set()
    names = [account]
    for acct in ledger.accounts:
        if acct.name == account:
            names.extend(acct.aliases)
    return {tok for name in names for tok in _TOKEN.findall(name.lower())}


def _usable(token: str, excluded: set[str]) -> bool:
    return (len(token) >= 3 and token not in STOPWORDS and token not in excluded
            and not token.isdigit() and not re.fullmatch(r"(?:q[1-4]|fy\d+|h[12])", token))


def anchored_terms(driver: str, account: str | None, ledger: Ledger) -> list[Term]:
    """Search terms derived from the stated reason itself, without a model."""
    lower = driver.lower()
    excluded = _account_tokens(account, ledger)
    # A lesson says what its trigger phrase means in the ledger, so the phrase's own words
    # are not also searched one by one: "board coverage" -> d&o must not let "coverage"
    # bind the claim to an unrelated cyber-coverage invoice as well.
    fired = [(expansions, [t for t in triggers if re.search(rf"(?<![a-z0-9]){re.escape(t)}", lower)])
             for _name, triggers, expansions in LEARNED]
    fired = [(expansions, hits) for expansions, hits in fired if hits]
    replaced = {tok for expansions, hits in fired for hit in hits
                for tok in _TOKEN.findall(hit) if tok not in expansions}
    terms: list[Term] = []
    seen: set[str] = set()
    for token in _TOKEN.findall(lower):
        token = token.strip("-'")
        if token.endswith("'s"):
            token = token[:-2]
        if _usable(token, excluded) and token not in seen and token not in replaced:
            seen.add(token)
            terms.append(Term(token, "quote"))
    for _name, triggers, expansions in LEXICON:
        if any(re.search(rf"(?<![a-z0-9]){re.escape(t)}", lower) for t in triggers):
            for expansion in expansions:
                if expansion not in seen:
                    seen.add(expansion)
                    terms.append(Term(expansion, "lexicon"))
    for expansions, _hits in fired:
        for expansion in expansions:
            if expansion not in seen:
                seen.add(expansion)
                terms.append(Term(expansion, "learned"))
    return terms


def term_pattern(term: str) -> re.Pattern[str]:
    """Word-bounded, tolerant of a plural or an inflection, never of an arbitrary prefix."""
    words = term.lower().split()
    last = words[-1]
    stem = last[:-1] if last.endswith("s") and len(last) > 4 and not last.endswith("ss") else last
    tail = "[a-z]*" if len(stem) >= 5 else "(?:s|es)?"
    body = r"\s+".join([re.escape(w) for w in words[:-1]] + [re.escape(stem) + tail])
    return re.compile(rf"(?<![a-z0-9]){body}(?![a-z0-9])")


# ── Proposals and claims ─────────────────────────────────────────────────

@dataclass(frozen=True)
class ClaimProposal:
    """What an extractor thinks a sentence claims. Untrusted, and has no verdict field."""

    quote: str
    account: str | None = None
    change_text: str | None = None
    percent_text: str | None = None
    prior_text: str | None = None
    current_text: str | None = None
    driver_text: str | None = None
    driver_terms: tuple[str, ...] = ()
    direction: str | None = None      # informational only; re-read from the quote
    extractor: str = "rules"


@dataclass(frozen=True)
class Rejection:
    quote: str
    reason: str
    extractor: str

    def to_dict(self) -> dict:
        return {"quote": self.quote, "reason": self.reason, "extractor": self.extractor}


@dataclass(frozen=True)
class Claim:
    claim_id: str
    start: int
    end: int
    quote: str
    account: str | None
    account_origin: str | None           # "alias" | "model" | None
    direction: int | None
    change: Figure | None
    percent: Figure | None
    prior: Figure | None
    current: Figure | None
    driver: str | None
    terms: tuple[Term, ...]
    strength: Strength
    extractor: str
    notes: tuple[str, ...] = field(default=())

    def to_dict(self) -> dict:
        def fig(f: Figure | None) -> dict | None:
            return f.to_dict() if f else None
        return {
            "claim_id": self.claim_id, "span": [self.start, self.end], "quote": self.quote,
            "account": self.account, "account_origin": self.account_origin,
            "direction": {1: "up", -1: "down"}.get(self.direction or 0),
            "stated": {"change": fig(self.change), "percent": fig(self.percent),
                       "prior": fig(self.prior), "current": fig(self.current)},
            "driver": self.driver, "terms": [t.to_dict() for t in self.terms],
            "strength": self.strength.value, "extractor": self.extractor,
            "notes": list(self.notes),
        }


def _figure_in(quote: str, text: str | None, parser) -> tuple[Figure | None, str | None]:
    """A proposed figure, if the quote really states it; else the reason it does not."""
    if not text:
        return None, None
    position = quote.find(text)
    if position < 0:
        return None, f"figure {text!r} does not occur in the quoted sentence"
    figure = parser(text)
    if figure is None:
        return None, f"{text!r} is not a single readable figure"
    return Figure(figure.text, figure.value, figure.half_unit, position,
                  position + len(text)), None


def admit(proposal: ClaimProposal, text: str, ledger: Ledger, claim_id: str,
          taken: set[int]) -> Claim | Rejection:
    """Grant or refuse a proposal, using only the explanation's own bytes."""
    quote = proposal.quote.strip()
    start = -1
    if quote:
        start = text.find(quote)
        while start >= 0 and start in taken:
            start = text.find(quote, start + 1)
    if start < 0:
        return Rejection(quote, "quote_not_in_text", proposal.extractor)

    reading = read_sentence(quote, ledger)
    notes: list[str] = []

    figures = {}
    for name, parser in (("change", parse_money), ("percent", parse_percent),
                         ("prior", parse_money), ("current", parse_money)):
        figure, problem = _figure_in(quote, getattr(proposal, f"{name}_text"), parser)
        if problem and name in ("change", "percent"):
            return Rejection(quote, "figure_not_in_quote", proposal.extractor)
        if problem:
            notes.append(f"{name} figure dropped: {problem}")
        figures[name] = figure

    names = set(ledger.account_names) | {TOTAL}
    account, origin = reading.account, ("alias" if reading.account else None)
    if proposal.account and proposal.account not in names:
        notes.append(f"proposed account {proposal.account!r} is not in the chart of accounts")
    elif proposal.account and account and proposal.account != account:
        notes.append(f"proposed account {proposal.account!r} overridden by the alias "
                     f"written in the sentence ({account})")
    elif proposal.account and account is None:
        account, origin = proposal.account, "model"

    if proposal.direction and reading.direction is None:
        notes.append("proposed direction dropped: no direction word in the sentence")

    driver = proposal.driver_text.strip() if proposal.driver_text else None
    if driver and driver not in quote:
        notes.append(f"proposed reason {driver!r} dropped: not a span of the sentence")
        driver = None

    terms: list[Term] = []
    if driver:
        terms = anchored_terms(driver, account, ledger)
        known = {t.text for t in terms}
        for raw in proposal.driver_terms:
            candidate = raw.strip().lower()
            if candidate and candidate not in known and candidate not in STOPWORDS \
                    and len(candidate) >= 3:
                known.add(candidate)
                terms.append(Term(candidate, "model"))

    if not any((figures["change"], figures["percent"], figures["prior"],
                figures["current"], driver, reading.direction)):
        return Rejection(quote, "no_assertion", proposal.extractor)

    taken.add(start)
    return Claim(
        claim_id=claim_id, start=start, end=start + len(quote), quote=quote,
        account=account, account_origin=origin, direction=reading.direction,
        change=figures["change"], percent=figures["percent"], prior=figures["prior"],
        current=figures["current"], driver=driver, terms=tuple(terms),
        strength=reading.strength, extractor=proposal.extractor, notes=tuple(notes),
    )
