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
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from proven import claims

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
    from proven.extract import RuleExtractor   # local: keeps `import proven.learned` cheap
    from proven.ledger import Ledger
    from proven.report import run
    from proven.server import load_scenario

    if case.get("ledger_csv"):
        book = Ledger.from_csv(case["ledger_csv"], entity=case.get("entity") or "Uploaded ledger")
    else:
        book = load_scenario(case["scenario_id"])["ledger"]
    with lexicon(lexicon_entries or []):
        report = run(case["explanation"], book, extractor=RuleExtractor())
    for result in report["claims"]:
        if result["claim"]["quote"] == case["quote"]:
            return result["verdict"]
    return None


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
