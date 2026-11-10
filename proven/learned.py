"""Reviewer-confirmed lexicon entries: what a reviewer teaches Proven, kept on disk.

A lesson says "when a stated reason contains any of these phrases, also search the
ledger for these words". It is stored in `<data_dir>/lexicon.jsonl` with where it
came from (run, claim, quote, the reviewer's note) and applied through
`claims.set_learned`, which gives its terms the origin "learned": anchored exactly
like the built-in lexicon, so they can support a PASS or a FAIL.

That power is why a lesson is validated hard and is never loaded implicitly. Nothing
here runs at import time; the benchmark and the tests see an empty `claims.LEARNED`
unless a caller applies a data directory on purpose.

Replay: a lesson taught from a resolution is stored with a case (the text, the
ledger, the claim's quote, and the verdict before and after). `replay()` re-runs
every case with the lexicon applied and reports the ones whose verdict has changed.
"""
from __future__ import annotations

import json
import re
import threading
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Iterator

from proven import claims

if TYPE_CHECKING:
    from proven.ledger import Ledger

LEXICON_FILE = "lexicon.jsonl"
RESOLUTIONS_FILE = "resolutions.jsonl"
MAX_PHRASES = 8
MAX_PHRASE_CHARS = 60
MIN_TERM_CHARS = 3

#: A plain word or phrase: letters, digits, and the joiners the term matcher understands.
_PLAIN = re.compile(r"[a-z0-9](?:[a-z0-9&'\- ]*[a-z0-9])?")

_lock = threading.RLock()


class LessonRefused(ValueError):
    """A lesson Proven will not learn. The message says why, for the reviewer."""


def _clean(kind: str, values: object) -> list[str]:
    if not isinstance(values, (list, tuple)):
        raise LessonRefused(f"{kind} must be a list of words or phrases")
    out: list[str] = []
    for raw in values:
        if not isinstance(raw, str):
            raise LessonRefused(f"{kind} must be text, not {type(raw).__name__}")
        phrase = " ".join(raw.lower().split())
        if not phrase:
            continue
        if len(phrase) > MAX_PHRASE_CHARS:
            raise LessonRefused(f"“{phrase[:20]}…” is longer than {MAX_PHRASE_CHARS} characters; "
                                "use a short word or phrase")
        if not _PLAIN.fullmatch(phrase):
            raise LessonRefused(f"“{phrase}” is not a plain word or phrase "
                                "(letters, digits, spaces, & ' - only; no patterns or punctuation)")
        if phrase not in out:
            out.append(phrase)
    return out


def _generic(phrase: str) -> bool:
    """True when every word of a phrase is a stopword or a number: it says nothing."""
    return all(word in claims.STOPWORDS or word.isdigit() for word in phrase.split())


def validate(triggers: object, terms: object) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Normalise a lesson, or refuse it with a reason a reviewer can act on."""
    trig = _clean("triggers", triggers)
    term = _clean("terms", terms)
    if not trig:
        raise LessonRefused("a lesson needs at least one trigger phrase (the words in the "
                            "stated reason that should lead to the ledger words)")
    if not term:
        raise LessonRefused("a lesson needs at least one ledger word to search for")
    if len(trig) > MAX_PHRASES or len(term) > MAX_PHRASES:
        raise LessonRefused(f"a lesson holds at most {MAX_PHRASES} triggers and {MAX_PHRASES} terms; "
                            "teach narrower lessons")
    for phrase in trig:
        if len(phrase) < MIN_TERM_CHARS:
            raise LessonRefused(f"trigger “{phrase}” is shorter than {MIN_TERM_CHARS} characters "
                                "and would fire on unrelated sentences")
        if _generic(phrase):
            raise LessonRefused(f"trigger “{phrase}” is made only of common words "
                                "and would fire on unrelated sentences")
    for phrase in term:
        if len(phrase) < MIN_TERM_CHARS:
            raise LessonRefused(f"term “{phrase}” is shorter than {MIN_TERM_CHARS} characters "
                                "and would match unrelated transactions")
        if phrase in claims.STOPWORDS:
            raise LessonRefused(f"term “{phrase}” is a common word the matcher ignores on purpose "
                                "(it would bind the claim to unrelated transactions); choose a "
                                "word that names the cause")
        if _generic(phrase):
            raise LessonRefused(f"term “{phrase}” is made only of common words; choose a word "
                                "that names the cause")
    return tuple(trig), tuple(term)


# ── storage ──────────────────────────────────────────────────────────────

def path(data_dir: Path | str) -> Path:
    return Path(data_dir) / LEXICON_FILE


def load(data_dir: Path | str) -> list[dict]:
    """Stored entries, oldest first. A line that no longer validates is skipped, not trusted."""
    file = path(data_dir)
    if not file.exists():
        return []
    entries = []
    for line in file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            validate(entry["triggers"], entry["terms"])
            entry["id"] = str(entry["id"])
        except (ValueError, KeyError, TypeError):
            continue
        entries.append(entry)
    return entries


def as_lexicon(entries: list[dict]) -> list[tuple[str, tuple[str, ...], tuple[str, ...]]]:
    return [(f"learned-{e['id']}", tuple(e["triggers"]), tuple(e["terms"])) for e in entries]


def apply(data_dir: Path | str) -> list[dict]:
    """Load the directory's lexicon and make it the active one. Returns the entries."""
    entries = load(data_dir)
    claims.set_learned(as_lexicon(entries))
    return entries


def make_entry(triggers: object, terms: object, *, note: str = "", run_id: str = "",
               claim_id: str = "", quote: str = "", action: str = "") -> dict:
    trig, term = validate(triggers, terms)
    return {"id": uuid.uuid4().hex[:10],
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "triggers": list(trig), "terms": list(term),
            "provenance": {"run_id": run_id, "claim_id": claim_id, "quote": quote,
                           "action": action, "note": note}}


# ── which ledger words a lesson may keep ─────────────────────────────────

ROUTINE_ONLY = ("matches only routine lines in this account (the same vendor and memo in both "
                "periods) that did not move")
NOT_NEEDED = "is not needed for this claim to pass"


@dataclass(frozen=True)
class Trimmed:
    """A lesson's ledger words after `trim_terms`: the ones kept, the ones dropped (each
    {"term", "reason"}), and the claim's verdict with the kept ones."""

    kept: list[str]
    dropped: list[dict]
    verdict: str | None


def routine_ids(ledger: Ledger, account: str) -> set[str]:
    """Transactions in the account whose vendor and memo also appear in the other period:
    the account's routine spending, the same bill in both months."""
    periods: dict[tuple[str, str], set[str]] = {}
    scope = ledger.in_scope(account)
    for txn in scope:
        periods.setdefault((txn.vendor, txn.memo), set()).add(txn.period)
    return {t.id for t in scope if len(periods[(t.vendor, t.memo)]) > 1}


def _hits(ledger: Ledger, account: str, term: str) -> list:
    pattern = claims.term_pattern(term)
    return [t for t in ledger.in_scope(account) if pattern.search(t.searchable)]


def _moved(ledger: Ledger, hits: list) -> float:
    return abs(sum(t.amount if t.period == ledger.current_period else -t.amount for t in hits))


def trim_terms(terms: list[str], ledger: Ledger, account: str | None,
               verdict: Callable[[list[str]], str | None],
               materiality: float | None = None) -> Trimmed:
    """The ledger words of a lesson that name its cause, read off the close it is taught on.

    A lesson's terms are anchored once learned: they bind every later claim whose reason
    fires the trigger, and can carry a PASS there. Confirming every term that matched
    something, because the claim then passes, is not enough. A model blind to the ledger
    guesses words such as a contractor's name; in the teaching close that word matched only
    the contractor's monthly servicing, the PASS did not need it, and in a later close it
    bound the same contractor's other job (the account's other cause) and passed a wrong
    explanation. When the lesson makes the claim PASS, three rules apply to that close:

      (a) ROUTINE ONLY. A word whose every match in the account is a routine line (the
          same vendor and memo in both periods) that moved by less than `materiality` is
          dropped: it found the bill that recurs, not what moved, so it says nothing about
          the stated cause. A recurring bill that did move ("the same bill, simply larger")
          is a cause, and its word is kept.
      (b) NOT NEEDED. Every remaining word the PASS does not need is dropped, trying first
          the word whose matches moved least. A word the PASS rests on has to be there; any
          other is a guess nothing in this close checked, and in a close where it matches
          another cause it would decide the claim.
      (c) PART OF A JOB. The kept words must cover all of a vendor's new charges (material,
          not routine) in a period, or none of them. A word that matches one of a vendor's
          two new charges that month found part of a job: the PASS then leaned on a second
          word, which matched part of the account's other cause, to clear the threshold of
          a hedged "primarily due to". Later, a "because of" sentence about the whole job
          matched only that part and FAILed as a partial explanation, and an explanation
          whose other charge was booked to the wrong account passed. Such a lesson is
          refused; no word can be dropped to mend it. Removing a word under (b) is likewise
          not allowed to leave part of a job uncovered.

    A lesson that does not make the claim PASS is left as it is: no word of it is hidden
    behind a PASS, and the safety gate replays it. `verdict(terms)` is the claim's verdict
    with the lesson holding those terms; the result's verdict is the one with the kept
    words, and is not PASS when the PASS rested on a dropped routine word (the caller
    refuses the lesson then). Raises `LessonRefused` when no word is left, or under (c)."""
    if materiality is None:
        from proven.verify import Policy            # local: keeps `import proven.learned` cheap
        materiality = Policy().materiality
    terms = list(terms)
    full = verdict(terms)
    if full != "PASS" or not account:
        return Trimmed(terms, [], full)
    kept: list[str] = []
    dropped: list[dict] = []
    routine = routine_ids(ledger, account)
    for term in terms:
        hits = _hits(ledger, account, term)
        if hits and {t.id for t in hits} <= routine and _moved(ledger, hits) < materiality:
            dropped.append({"term": term, "reason": ROUTINE_ONLY})
        else:
            kept.append(term)
    if not kept:
        raise LessonRefused("every word " + ROUTINE_ONLY + "; none of them names the stated cause")
    result = verdict(kept) if dropped else full
    if result != "PASS":
        return Trimmed(kept, dropped, result)
    moved = {t: _moved(ledger, _hits(ledger, account, t)) for t in kept}
    for term in sorted(kept, key=lambda t: moved[t]):     # stable: ties keep their order
        if len(kept) == 1:
            break
        trial = [t for t in kept if t != term]
        if (_part_of_a_job(ledger, account, trial, routine, materiality) is None
                and verdict(trial) == "PASS"):
            kept = trial
            dropped.append({"term": term, "reason": NOT_NEEDED})
    split = _part_of_a_job(ledger, account, kept, routine, materiality)
    if split:
        raise LessonRefused(split)
    return Trimmed(kept, dropped, result)


def _part_of_a_job(ledger: Ledger, account: str, words: list[str], routine: set[str],
                   materiality: float) -> str | None:
    """Why `words` cover only part of a vendor's new charges in a period, or None (rule c)."""
    new = [t for t in ledger.in_scope(account)
           if t.id not in routine and abs(t.amount) >= materiality]
    found: dict[str, str] = {}
    for word in words:
        for txn in _hits(ledger, account, word):
            found.setdefault(txn.id, word)
    for txn in new:
        if txn.id in found:
            continue
        sibling = next((t for t in new if t.id in found and t.vendor == txn.vendor
                        and t.period == txn.period), None)
        if sibling is not None:
            return (f"\u201c{found[sibling.id]}\u201d matches only part of {txn.vendor}'s new charges "
                    f"in {txn.period} (not \u201c{txn.memo}\u201d): a lesson must cover all of a "
                    "job or none of it")
    return None


def trim_text(trimmed: Trimmed) -> str:
    """Why a lesson's words were dropped, and what to teach instead, for the reviewer."""
    parts = "; ".join(f"\u201c{d['term']}\u201d {d['reason']}" for d in trimmed.dropped)
    if trimmed.verdict != "PASS":
        return (f"{parts}, and without it the claim does not pass ({trimmed.verdict}): "
                "the pass rests on a bill that did not move.")
    keep = ", ".join(f"\u201c{t}\u201d" for t in trimmed.kept)
    return f"{parts}. Teach the lesson with only {keep}."


def append(data_dir: Path | str, entry: dict) -> dict:
    """Store a made entry, refusing one that duplicates a stored lesson."""
    with _lock:
        for existing in load(data_dir):
            if (set(existing["triggers"]) == set(entry["triggers"])
                    and set(existing["terms"]) == set(entry["terms"])):
                raise LessonRefused(f"Proven already learned this (lesson {existing['id']})")
        Path(data_dir).mkdir(parents=True, exist_ok=True)
        with path(data_dir).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
    return entry


def remove(data_dir: Path | str, entry_id: str) -> dict:
    """Delete one lesson. Raises KeyError if there is no such lesson."""
    with _lock:
        entries = load(data_dir)
        gone = next((e for e in entries if e["id"] == entry_id), None)
        if gone is None:
            raise KeyError(entry_id)
        file = path(data_dir)
        tmp = file.with_suffix(".tmp")
        tmp.write_text("".join(json.dumps(e) + "\n" for e in entries if e is not gone),
                       encoding="utf-8")
        tmp.replace(file)
    return gone


@contextmanager
def lexicon(entries: list[dict]) -> Iterator[None]:
    """Apply entries for the duration of a block, then put back whatever was active."""
    with _lock:
        previous = list(claims.LEARNED)
        claims.set_learned(as_lexicon(entries))
        try:
            yield
        finally:
            claims.set_learned(previous)


# ── regression cases ─────────────────────────────────────────────────────

def case_verdict(case: dict, lexicon_entries: list[dict] | None = None) -> str | None:
    """Verdict of the case's claim with the given lexicon applied (none if the claim is gone).

    Always uses the offline rule extractor: a regression case must be deterministic.
    """
    result = case_result(case, lexicon_entries)
    return None if result is None else result["verdict"]


def case_ledger(case: dict) -> Ledger:
    """The ledger a case's claim was checked against."""
    from proven.ledger import Ledger            # local: keeps `import proven.learned` cheap
    from proven.server import load_scenario

    if case.get("ledger_csv"):
        return Ledger.from_csv(case["ledger_csv"], entity=case.get("entity") or "Uploaded ledger")
    return load_scenario(case["scenario_id"])["ledger"]


def case_result(case: dict, lexicon_entries: list[dict] | None = None,
                book: Ledger | None = None) -> dict | None:
    """The case's claim, checked by the offline rule extractor with the given lexicon."""
    from proven.extract import RuleExtractor
    from proven.report import run

    book = book if book is not None else case_ledger(case)
    with lexicon(lexicon_entries or []):
        report = run(case["explanation"], book, extractor=RuleExtractor())
    return next((r for r in report["claims"] if r["claim"]["quote"] == case["quote"]), None)


def trim_case(case: dict, triggers: list[str], terms: list[str],
              lexicon_entries: list[dict]) -> Trimmed:
    """`trim_terms` for a lesson taught on a case, judged as the console judges it: the
    rule extractor reading the case with the lessons already held plus this one."""
    book = case_ledger(case)
    seen: dict[tuple[str, ...], dict | None] = {}

    def result(words: list[str]) -> dict | None:
        key = tuple(words)
        if key not in seen:
            seen[key] = case_result(case, lexicon_entries + [make_entry(triggers, words)], book)
        return seen[key]

    def verdict(words: list[str]) -> str | None:
        found = result(words)
        return None if found is None else found["verdict"]

    first = result(list(terms))
    account = first["claim"].get("account") if first else None
    return trim_terms(list(terms), book, account, verdict)


def cases(data_dir: Path | str) -> list[dict]:
    """Every stored resolution that taught something, with its case."""
    file = Path(data_dir) / RESOLUTIONS_FILE
    if not file.exists():
        return []
    out = []
    for line in file.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entry = json.loads(line)
            if entry.get("case") and entry.get("lesson_id"):
                out.append(entry)
    return out


def replay(data_dir: Path | str) -> list[dict]:
    """Re-verify every taught case under the current lexicon.

    Each result: the resolution's lesson id and quote, the verdict the reviewer saw
    after teaching (`expected`), the verdict now (`actual`), whether the lesson is
    still stored, and `ok`.
    """
    entries = load(data_dir)
    active = {e["id"] for e in entries}
    results = []
    for resolution in cases(data_dir):
        case = resolution["case"]
        actual = case_verdict(case, entries)
        results.append({"lesson_id": resolution["lesson_id"], "quote": case["quote"],
                        "before": case.get("verdict_before"), "expected": case.get("verdict_after"),
                        "actual": actual, "lesson_active": resolution["lesson_id"] in active,
                        "ok": actual == case.get("verdict_after")})
    return results
