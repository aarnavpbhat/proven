"""The lesson safety gate: replay a lesson against known answers before it is trusted.

A lesson ("when a stated reason says X, search the ledger for Y") gives its terms the
origin "learned", which can support a PASS. `learned.validate` refuses lessons that are
malformed or made of common words; it cannot tell a right lesson from a wrong one. A
reviewer confirming in a hurry can teach "the second location" -> "build-out", and from
then on a wrong explanation of a rent increase passes. This module is the check that
runs before a lesson is stored:

  * the REGRESSION SET: claims from synthetic closes of the TRAIN split, every defect
    family and every control family, in all three phrasings. The test split is never
    used, so the benchmark and the teaching simulation stay honest. It is generated
    deterministically, read once by the rule extractor, and kept in process.
  * the data directory's own STORED CASES: every resolution recorded with its text and
    ledger. A reviewer's "Confirm defect" is a known-wrong explanation; a taught case is
    a known-right one.

The candidate lesson is replayed with the lessons already active, and only on claims it
can change: those whose stated reason it fires on, or that contain one of its terms as
a written word (a learned term vouches for that word in `verify._weak_binding`). Every
other claim's verdict is provably the same with or without it.

A lesson is REFUSED when, compared with the lexicon without it, it would

  * PASS an explanation known to be wrong (a regression defect, or a stored case a
    reviewer confirmed as a defect), or
  * FAIL an explanation known to be right (a regression control, or a stored case that
    was taught as right and passed).

Everything else is reported, not refused: how many known-correct claims it newly
decides, how many defects it newly fails, which stored cases change verdict, and how
many claims it touched at all. A lesson that touches nothing in either set was not
tested by the gate, and the report says so rather than calling it safe.

WHAT IT CANNOT DO. The regression set is synthetic and shares an author with the
generator and the checker. A phrase that appears in neither the set nor the stored
cases passes the gate untested. Its value is in proportion to how much of the
reviewer's vocabulary those two sets cover.
"""
from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from proven import learned
from proven.claims import ClaimProposal, Rejection, admit
from proven.extract import RuleExtractor
from proven.ledger import Ledger
from proven.synth import PHRASINGS, generate_split
from proven.verify import verify_claim

REGRESSION_SPLIT = "train"
#: Train closes per phrasing. 880 is 80 per family per phrasing; building the set takes a
#: few seconds once per process, and a check afterwards takes milliseconds.
REGRESSION_CLOSES = 880
MAX_EXAMPLES = 5

#: Resolution actions that say the explanation was wrong, and those that say it was right
#: (the teaching actions: "Proven should have known this").
WRONG_ACTIONS = frozenset({"confirm_defect"})
RIGHT_ACTIONS = frozenset({"fix_evidence", "fix_reading", "accept_convention"})


@dataclass(frozen=True)
class Probe:
    """One claim with a known answer, read once by the rule extractor."""

    explanation: str
    ledger: Ledger
    proposal: ClaimProposal
    quote: str
    driver: str                 # the stated reason, lower case
    known: str                  # "wrong" | "right"
    source: str                 # "regression" | "case"
    family: str                 # synthetic family, or the reviewer's action for a case
    phrasing: str               # synthetic phrasing tier, or "" for a case
    ref: str                    # scenario id, or the case's lesson / run reference
    expected: str | None = None  # a stored case: the verdict the reviewer saw after deciding


def fires(trigger: str, driver: str) -> bool:
    """Exactly the test `claims.anchored_terms` uses to decide that a lesson applies."""
    return re.search(rf"(?<![a-z0-9]){re.escape(trigger)}", driver) is not None


def touches(lesson: dict, driver: str) -> bool:
    """Can this lesson change the verdict of a claim whose stated reason is `driver`?

    Yes if a trigger fires on it, or if one of its terms occurs in it (a learned term
    vouches for the same word written in a sentence). A superset on purpose: a false
    "yes" costs one extra replay, a false "no" would skip a claim the lesson changes."""
    return (any(fires(t, driver) for t in lesson["triggers"])
            or any(term in driver for term in lesson["terms"]))


def _verdict(probe: Probe) -> str | None:
    admitted = admit(probe.proposal, probe.explanation, probe.ledger, "C1", set())
    if isinstance(admitted, Rejection):
        return None
    return verify_claim(admitted, probe.ledger).verdict.value


def probes_for(explanation: str, ledger: Ledger, wanted: list[tuple[str, dict]]) -> list[Probe]:
    """Probes for the given quotes of one close: (quote, fields) pairs. Quotes the rule
    extractor does not read, or that state no reason, are skipped: no lesson can move them."""
    by_quote = {p.quote: p for p in RuleExtractor().propose(explanation, ledger)}
    out = []
    for quote, fields in wanted:
        proposal = by_quote.get(quote)
        if proposal is None or not proposal.driver_text:
            continue
        out.append(Probe(explanation, ledger, proposal, quote, proposal.driver_text.lower(), **fields))
    return out


# ── the built-in regression set ─────────────────────────────────────────

_lock = threading.Lock()
_regression: tuple[list[Probe], dict] | None = None


def regression_set(n: int = REGRESSION_CLOSES) -> tuple[list[Probe], dict]:
    """(probes, description). Built on first use and kept for the life of the process."""
    global _regression
    with _lock:
        if _regression is not None and _regression[1]["closes_per_phrasing"] == n:
            return _regression
        started = time.perf_counter()
        probes: list[Probe] = []
        closes = 0
        for phrasing in PHRASINGS:
            for scenario in generate_split(REGRESSION_SPLIT, n, phrasing):
                closes += 1
                probes.extend(probes_for(scenario.explanation, scenario.ledger, [
                    (label.quote, {"known": "right" if label.requirement == "PASS" else "wrong",
                                   "source": "regression", "family": label.family,
                                   "phrasing": phrasing, "ref": scenario.scenario_id})
                    for label in scenario.labels]))
        info = {"split": REGRESSION_SPLIT, "phrasings": list(PHRASINGS), "closes_per_phrasing": n,
                "closes": closes, "claims": len(probes),
                "known_wrong": sum(p.known == "wrong" for p in probes),
                "known_right": sum(p.known == "right" for p in probes),
                "build_ms": round((time.perf_counter() - started) * 1000, 1)}
        _regression = (probes, info)
        return _regression


# ── the data directory's own cases ───────────────────────────────────────

_case_cache: dict[str, tuple[tuple[float, int], list[Probe]]] = {}


def stored_cases(data_dir: Path | str) -> list[Probe]:
    """Every recorded resolution with its text and ledger, as a probe with a known answer.

    "Confirm defect" is known wrong. A teaching action is known right when the claim ended
    PASS (or was not refuted) after the reviewer decided. Other actions say nothing about
    whether the explanation is right and are not used."""
    from proven.server import BadRequest, load_scenario   # local: the server imports this module

    file = Path(data_dir) / learned.RESOLUTIONS_FILE
    if not file.exists():
        return []
    stat = file.stat()
    stamp = (stat.st_mtime, stat.st_size)
    cached = _case_cache.get(str(file))
    if cached and cached[0] == stamp:
        return cached[1]
    probes: list[Probe] = []
    for line in file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        case, action = entry.get("case"), entry.get("action")
        if not isinstance(case, dict) or not case.get("quote") or not case.get("explanation"):
            continue
        if action in WRONG_ACTIONS:
            known = "wrong"
        elif action in RIGHT_ACTIONS and case.get("verdict_after", "PASS") == "PASS":
            known = "right"
        else:
            continue
        try:
            if case.get("ledger_csv"):
                book = Ledger.from_csv(case["ledger_csv"], entity=case.get("entity") or "Uploaded ledger")
            else:
                book = load_scenario(str(case.get("scenario_id", "")))["ledger"]
        except (BadRequest, ValueError, KeyError):
            continue
        probes.extend(probes_for(case["explanation"], book, [(case["quote"], {
            "known": known, "source": "case", "family": str(action), "phrasing": "",
            "ref": str(entry.get("lesson_id") or entry.get("run_id") or ""),
            "expected": case.get("verdict_after")})]))
    _case_cache[str(file)] = (stamp, probes)
    return probes


# ── the check ────────────────────────────────────────────────────────────

def _example(probe: Probe, before: str | None, after: str | None) -> dict:
    return {"quote": probe.quote, "source": probe.source, "family": probe.family,
            "phrasing": probe.phrasing, "ref": probe.ref, "before": before, "after": after}


def impact(lesson: dict, active: list[dict], cases: list[Probe] | None = None, *,
           regression: bool = True) -> dict:
    """Replay `lesson` on top of `active` and report what it would change.

    `lesson` and `active` are lexicon entries (`learned.make_entry`). The result's
    `accepted` is False when the lesson would pass known-wrong work or fail known-right
    work; `refusal` then says why in plain words, with examples."""
    started = time.perf_counter()
    base = [e for e in active if e.get("id") != lesson.get("id")]
    pool, info = regression_set() if regression else ([], {})
    pool = list(pool) + list(cases or [])
    touched = [p for p in pool if touches(lesson, p.driver)]
    with learned.lexicon(base):
        before = [_verdict(p) for p in touched]
    with learned.lexicon(base + [lesson]):
        after = [_verdict(p) for p in touched]

    reg = {"touched": 0, "touched_wrong": 0, "touched_right": 0, "new_unsafe_passes": 0,
           "new_control_fails": 0, "newly_passed_right": 0, "newly_failed_wrong": 0,
           "unpassed_right": 0, "examples": []}
    stored = {"n": sum(1 for p in pool if p.source == "case"), "touched": 0, "changed": [],
              "new_unsafe_passes": 0, "new_control_fails": 0}
    blocking: list[dict] = []
    for probe, b, a in zip(touched, before, after):
        bucket = reg if probe.source == "regression" else stored
        bucket["touched"] += 1
        if probe.source == "regression":
            reg["touched_wrong" if probe.known == "wrong" else "touched_right"] += 1
        if b == a:
            continue
        unsafe = probe.known == "wrong" and a == "PASS"
        false_fail = probe.known == "right" and a == "FAIL"
        if unsafe:
            bucket["new_unsafe_passes"] += 1
        if false_fail:
            bucket["new_control_fails"] += 1
        if unsafe or false_fail:
            blocking.append(_example(probe, b, a))
        if probe.source == "case":
            stored["changed"].append({**_example(probe, b, a), "known": probe.known,
                                      "expected": probe.expected})
            continue
        if probe.known == "right" and a == "PASS":
            reg["newly_passed_right"] += 1
        elif probe.known == "right" and b == "PASS":
            reg["unpassed_right"] += 1
        elif probe.known == "wrong" and a == "FAIL":
            reg["newly_failed_wrong"] += 1
        if len(reg["examples"]) < MAX_EXAMPLES and not (unsafe or false_fail):
            reg["examples"].append(_example(probe, b, a))

    accepted = not blocking
    blocking.sort(key=lambda b: b["after"] != "PASS")     # a wrong explanation passing leads
    return {
        "lesson": {"triggers": list(lesson["triggers"]), "terms": list(lesson["terms"])},
        "accepted": accepted,
        "refusal": None if accepted else refusal_text(blocking),
        "blocking": blocking[:MAX_EXAMPLES],
        "blocking_count": len(blocking),
        "regression": reg,
        "cases": stored,
        "tested": bool(reg["touched"] or stored["touched"]),
        "regression_set": info,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
    }


def refusal_text(blocking: list[dict]) -> str:
    """Why a lesson was refused, for the reviewer: what it would break, with one example."""
    wrong = [b for b in blocking if b["after"] == "PASS"]
    right = [b for b in blocking if b["after"] == "FAIL"]
    parts = []
    if wrong:
        parts.append(f"it would make {len(wrong)} explanation{'s' if len(wrong) != 1 else ''} "
                     "known to be wrong pass")
    if right:
        parts.append(f"it would fail {len(right)} explanation{'s' if len(right) != 1 else ''} "
                     "known to be right")
    first = (wrong or right)[0]
    where = ("a sentence you confirmed as a defect" if first["source"] == "case" and first["after"] == "PASS"
             else "a sentence taught as right" if first["source"] == "case"
             else f"synthetic regression close {first['ref']}, {first['family'].replace('_', ' ')}")
    return (f"Proven will not learn this: {' and '.join(parts)}. For example, “{first['quote']}” "
            f"({where}) would go from {first['before']} to {first['after']}. The trigger probably "
            "covers more than this cause, or the ledger words also match another cause's "
            "transactions; narrow the trigger to the words that name this cause, or choose words "
            "that appear only in its memos.")
