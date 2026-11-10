"""Other worlds: charts of accounts, vendors, memos and causes the default generator never had.

WHY. `proven.synth` writes every close from one world: nine accounts, eighteen causes, a
fixed set of vendors and memo wordings. A proposer trained on closes from that world can
score well by remembering which bookkeeping words go with which cause. That is not the
skill a reviewer needs from it, and a result measured in the same world cannot tell the
two apart. A world file moves all of it: the accounts, who bills them, what happens to
them, how the books word it and how a writer describes it.

A world is a JSON file:

    {"slug": "harbor-freight", "industry": "...", "author": "<who wrote it>",
     "entities": ["...", ...],
     "accounts": [{"name": "...", "aliases": [...], "narrative": [...],
                   "recurring": [{"vendor": "...", "base": 4200, "memo": "..."}],
                   "events": [{"key": "...", "vendor": "...", "memos": ["...", "..."],
                               "plain": ["..."], "oblique": ["...", ...],
                               "low": 12000, "high": 30000, "cross_memo": "..."},
                              {...}]}]}

`plain` phrases use the books' own words (the generator's "seen" tier). `oblique` phrases
describe the cause without any word the books use for it, which is where a proposer has
to supply the bookkeeping words itself.

WHAT `load` ENFORCES. The same rules `tests/test_synth.py` enforces on the default world,
applied to text nobody hand-checked: a plain phrase must bind to every row of its own
cause and to none of its sibling's or the account's routine spending; an oblique phrase
must bind to nothing in its own account, must not fire the built-in lexicon and must
survive the sentence reader intact. Phrases that break a rule are dropped; an account
left without two usable causes is dropped; a world left with fewer than `MIN_ACCOUNTS`
accounts is refused. `report` says what was dropped.

TIERS. For a measured world the valid oblique phrases of each cause are dealt in file
order: the first two are the "heldout" tier, the next four the test half of "paraphrase",
the rest its train half. For a training world (`role="train"`) every oblique phrase is
available to the train split and no test-split close should be drawn from it.

Directories: `proven/examples/worlds/` holds the measured worlds (`suite("unseen")`);
training worlds live with the training code and are loaded by path.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from proven.claims import STOPWORDS, _TOKEN, anchored_terms, resolve_account, split_reason, term_pattern
from proven.ledger import Account, Ledger
from proven.synth import AccountSpec, Event, Recurring, World, cause_terms

HERE = Path(__file__).parent / "examples" / "worlds"
MIN_ACCOUNTS = 5
HELDOUT_N, PARAPHRASE_TEST_N, PARAPHRASE_TRAIN_MIN = 2, 4, 2
_MONTHS = re.compile(r"\b(january|february|march|april|may|june|july|august|september|"
                     r"october|november|december)\b", re.I)


class WorldRefused(ValueError):
    """The file does not hold enough valid material to generate closes from."""


@dataclass
class Report:
    slug: str
    accounts_kept: int = 0
    accounts_dropped: list[str] = field(default_factory=list)
    plain_dropped: int = 0
    oblique_dropped: int = 0
    oblique_kept: int = 0
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def _binds(phrase: str, account: str, ledger: Ledger, text: str) -> bool:
    terms = anchored_terms(phrase, account, ledger)
    return any(term_pattern(t.text).search(text.lower()) for t in terms)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).strip()


def _event(raw: dict) -> Event:
    memos = tuple(_clean(m) for m in raw["memos"])[:2]
    if len(memos) != 2:
        raise ValueError("needs two memos")
    low = float(min(max(float(raw["low"]), 8000), 60000))
    high = float(min(max(float(raw["high"]), low * 1.6), low * 3))
    return Event(_clean(raw["key"]), _clean(raw["vendor"]), memos,
                 tuple(_clean(p) for p in raw.get("plain", [])), int(low), int(high),
                 _clean(raw["cross_memo"]))


def _spec(raw: dict) -> tuple[AccountSpec, dict[str, list[str]]]:
    name = _clean(raw["name"])
    aliases = tuple(dict.fromkeys(_clean(a).lower() for a in raw["aliases"] if _clean(a)))
    narrative = tuple(n for n in (_clean(x) for x in raw["narrative"]) if n.lower() in aliases)
    recurring = tuple(Recurring(_clean(r["vendor"]), float(min(max(float(r["base"]), 500), 40000)),
                                _clean(r["memo"])) for r in raw["recurring"])
    events = tuple(_event(e) for e in raw["events"])
    if len(events) != 2 or not narrative or len(recurring) < 2:
        raise ValueError("needs two events, two recurring vendors and a narrative alias")
    oblique = {e.key: [_clean(p) for p in r.get("oblique", [])] for e, r in zip(events, raw["events"])}
    return AccountSpec(name, aliases, narrative, recurring, events), oblique  # type: ignore[arg-type]


def _check_account(spec: AccountSpec, oblique: dict[str, list[str]], ledger: Ledger,
                   report: Report, need_oblique: int) -> tuple[AccountSpec, dict[str, list[str]]] | None:
    a, b = spec.events
    routine = [f"{r.vendor} {r.memo}" for r in spec.recurring]
    vendors = {r.vendor for r in spec.recurring}
    if a.vendor not in vendors or b.vendor in vendors or a.key == b.key:
        report.notes.append(f"{spec.name}: first cause must be billed by a recurring vendor, "
                            f"the second by a new one")
        return None
    kept_events, kept_oblique = [], {}
    for this, other in ((a, b), (b, a)):
        own = [f"{this.vendor} {memo}" for memo in this.memos] + [this.cross_memo]
        foreign = [f"{other.vendor} {memo}" for memo in other.memos] + routine
        plain = []
        for phrase in this.phrases:
            ok = (all(_binds(phrase, spec.name, ledger, t) for t in own)
                  and not any(_binds(phrase, spec.name, ledger, t) for t in foreign)
                  and split_reason(f"Costs rose $10K due to {phrase}.")[1] == phrase
                  and not _MONTHS.search(phrase))
            plain.append(phrase) if ok else None
            report.plain_dropped += not ok
        if not plain:
            # The author's plain phrases all failed; the words every row of the cause shares
            # are a plain phrase by construction ("the reefer overhaul").
            rows = [set(_TOKEN.findall(t.lower())) for t in [*this.memos, this.cross_memo]]
            shared = [t for t in _TOKEN.findall(this.memos[0].lower())
                      if all(t in row for row in rows) and len(t) >= 3 and t not in STOPWORDS
                      and not any(c.isdigit() for c in t)]
            candidate = "the " + " ".join(dict.fromkeys(shared[:3]))
            if shared and all(_binds(candidate, spec.name, ledger, t) for t in own) \
                    and not any(_binds(candidate, spec.name, ledger, t) for t in foreign) \
                    and split_reason(f"Costs rose $10K due to {candidate}.")[1] == candidate:
                plain.append(candidate)
                report.notes.append(f"{spec.name}/{this.key}: plain phrase derived from the memos")
        good = []
        for phrase in dict.fromkeys(oblique.get(this.key, [])):
            ok = (not any(_binds(phrase, spec.name, ledger, t) for t in own + [this.vendor] + foreign)
                  and not [t for t in anchored_terms(phrase, spec.name, ledger) if t.origin != "quote"]
                  and split_reason(f"Costs rose $10K due to {phrase}.")[1] == phrase
                  and not _MONTHS.search(phrase)
                  and phrase.lower() not in {p.lower() for p in this.phrases})
            good.append(phrase) if ok else None
            report.oblique_dropped += not ok
        if not plain or len(good) < need_oblique or len(cause_terms(spec, this)) < 2:
            report.notes.append(f"{spec.name}/{this.key}: {len(plain)} plain, {len(good)} oblique, "
                                f"{len(cause_terms(spec, this))} distinguishing memo words")
            return None
        kept_events.append(Event(this.key, this.vendor, this.memos, tuple(plain), this.low,
                                 this.high, this.cross_memo))
        kept_oblique[this.key] = good
    return AccountSpec(spec.name, spec.aliases, spec.narrative, spec.recurring,
                       (kept_events[0], kept_events[1])), kept_oblique


def build(data: dict, role: str = "measure") -> tuple[World, Report]:
    """A `World` from parsed JSON. `role` is "measure" (tiers dealt out) or "train"."""
    slug = _clean(data["slug"])
    report = Report(slug)
    parsed: list[tuple[AccountSpec, dict[str, list[str]]]] = []
    names: set[str] = set()
    alias_owner: dict[str, str] = {}
    keys: set[str] = set()
    for raw in data["accounts"]:
        try:
            spec, oblique = _spec(raw)
        except (KeyError, ValueError, TypeError) as error:
            report.accounts_dropped.append(f"{raw.get('name', '?')}: {error}")
            continue
        clash = [a for a in (spec.name.lower(), *spec.aliases) if a in alias_owner]
        if spec.name in names or clash or keys & {e.key for e in spec.events}:
            report.accounts_dropped.append(f"{spec.name}: name, alias or cause key already used")
            continue
        names.add(spec.name)
        keys |= {e.key for e in spec.events}
        for alias in (spec.name.lower(), *spec.aliases):
            alias_owner[alias] = spec.name
        parsed.append((spec, oblique))
    chart = tuple(Account(s.name, s.aliases) for s, _ in parsed)
    ledger = Ledger(slug, "2026-09", "2026-10", chart, ())
    need = (HELDOUT_N + PARAPHRASE_TEST_N + PARAPHRASE_TRAIN_MIN) if role == "measure" else 3
    specs: list[AccountSpec] = []
    heldout: dict[str, tuple[str, ...]] = {}
    p_train: dict[str, tuple[str, ...]] = {}
    p_test: dict[str, tuple[str, ...]] = {}
    for spec, oblique in parsed:
        # an alias that reads as a different account when a sentence opens with it is unusable
        if any(resolve_account(f"{n} rose $10K", ledger) != spec.name for n in spec.narrative):
            report.accounts_dropped.append(f"{spec.name}: a narrative alias resolves to another account")
            continue
        checked = _check_account(spec, oblique, ledger, report, need)
        if checked is None:
            report.accounts_dropped.append(spec.name)
            continue
        spec, good = checked
        specs.append(spec)
        for key, phrases in good.items():
            report.oblique_kept += len(phrases)
            if role == "measure":
                heldout[key] = tuple(phrases[:HELDOUT_N])
                p_test[key] = tuple(phrases[HELDOUT_N:HELDOUT_N + PARAPHRASE_TEST_N])
                p_train[key] = tuple(phrases[HELDOUT_N + PARAPHRASE_TEST_N:])
            else:
                heldout[key] = p_test[key] = p_train[key] = tuple(phrases)
    report.accounts_kept = len(specs)
    entities = tuple(_clean(e) for e in data.get("entities", []) if _clean(e))
    if len(specs) < MIN_ACCOUNTS or not entities:
        raise WorldRefused(f"{slug}: {len(specs)} usable accounts (need {MIN_ACCOUNTS}); "
                           + "; ".join(report.notes[:6]))
    # dropping an account changes the chart, and with it which words are the account's own
    return World(slug, tuple(specs), entities, heldout, p_train, p_test), report


def load(path: str | Path, role: str = "measure") -> World:
    return build(json.loads(Path(path).read_text(encoding="utf-8")), role)[0]


def suite(name: str = "unseen", root: Path | None = None) -> list[World]:
    """The measured worlds shipped under `examples/worlds/<name>/`, in file-name order.
    `PROVEN_WORLDS_DIR` points it at another directory of suites (the dev worlds, say)."""
    import os
    folder = (root or Path(os.environ.get("PROVEN_WORLDS_DIR") or HERE)) / name
    files = sorted(folder.glob("*.json"))
    if not files:
        raise FileNotFoundError(f"no world files in {folder}")
    return [load(f) for f in files]


def vocabulary(world: World) -> dict[str, set[str]]:
    """For overlap audits: the words a world's books and writers use.

    `terms` are the distinguishing memo words of each cause (what a proposer must supply),
    `vendors` the vendor names, `phrases` every way a cause is described."""
    terms, vendors, phrases = set(), set(), set()
    for spec in world.specs:
        vendors |= {r.vendor.lower() for r in spec.recurring}
        for event in spec.events:
            terms |= set(cause_terms(spec, event))
            vendors.add(event.vendor.lower())
            for bank in (event.phrases, world.heldout[event.key], world.paraphrase_train[event.key],
                         world.paraphrase_test[event.key]):
                phrases |= {p.lower() for p in bank}
    return {"terms": terms, "vendors": vendors, "phrases": phrases}
