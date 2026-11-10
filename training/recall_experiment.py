"""Experiment: re-offer the words a reviewer already confirmed for an account.

    python training/recall_experiment.py --suite dev --models proven-qwen3b-worlds2 claude-sonnet-5-5

A cause is described in many ways, and a lesson binds one of them: "the relocation" ->
`holdover`. When the next close says "paying two landlords at once" about the same account,
a blind proposer has to guess the book wording again from nothing. With recall, the teaching
loop adds the words of lessons already confirmed FOR THAT ACCOUNT to the proposer's guesses.
They are offered exactly as a model's guess is: origin "model", so the claim still waits in
REVIEW, the reviewer still confirms, and `learned.trim_terms` still keeps only the words the
PASS needs. Nothing changes at measurement: the held half is decided by rules and lessons.

This is a property of the loop, not of a model, so every proposer is run both ways. It is
NOT part of the benchmark protocol and not in the product. What it risks is what the
reviewer is shown: `exposed` counts wrong explanations in the taught half that reach
"supported by the proposed terms" (a careless reviewer could confirm those). Reported next
to the gain, per proposer.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from proven import learned, netguard, worlds  # noqa: E402
from proven.budget import Budget  # noqa: E402
from proven.evaluate import OracleExtractor  # noqa: E402
from proven.extract import RuleExtractor  # noqa: E402
from proven.extractors import build  # noqa: E402
from proven.report import run  # noqa: E402
from proven.synth import generate_split  # noqa: E402
from proven.teachsim import MODEL_SUPPORT, measure, trimmed_lesson  # noqa: E402

RECALLED = 8        # at most this many recalled words per claim, most recently confirmed first


class Recall:
    """A proposer whose claims also carry the account's confirmed words."""

    def __init__(self, inner, bank: dict[str, list[str]]):
        self.inner, self.bank = inner, bank
        self.name, self.version = inner.name, inner.version

    def propose(self, text, ledger):
        out = []
        for p in self.inner.propose(text, ledger):
            known = self.bank.get(p.account or "", [])
            if p.driver_text and known:
                p = replace(p, driver_terms=tuple(dict.fromkeys([*p.driver_terms, *known[::-1][:RECALLED]])))
            out.append(p)
        return out


def teach(pool, proposer_for, recall: bool) -> tuple[list[dict], int]:
    """`teachsim.teach`, optionally with recall; also how many wrong explanations were
    shown to the reviewer as supported by proposed terms."""
    lessons: list[dict] = []
    bank: dict[str, list[str]] = {}
    known, exposed = set(), 0
    for scenario in pool:
        proposer = Recall(proposer_for(scenario), bank) if recall else proposer_for(scenario)
        with learned.lexicon(lessons):
            report = run(scenario.explanation, scenario.ledger, extractor=proposer)
        labels = {label.quote: label for label in scenario.labels}
        for result in report["claims"]:
            label = labels.get(result["claim"]["quote"])
            waiting = (result["verdict"] == "REVIEW"
                       and any(f["code"] == MODEL_SUPPORT for f in result["findings"]))
            if label is None or not waiting:
                continue
            if label.requirement != "PASS":
                exposed += 1
                continue
            matched = (result["reconstruction"].get("driver") or {}).get("matched", [])
            terms = sorted({m["term"] for m in matched if m["origin"] == "model"})
            made = trimmed_lesson(scenario, lessons, result, terms, proposer)
            if made is None or made[1] != "PASS":
                continue
            entry = made[0]
            key = (tuple(entry["triggers"]), tuple(entry["terms"]))
            if key not in known:
                known.add(key)
                lessons.append(entry)
                words = bank.setdefault(result["claim"].get("account") or "", [])
                words += [t for t in entry["terms"] if t not in words]
    return lessons, exposed


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--suite", default="dev")
    p.add_argument("--models", nargs="+", required=True, help='cached proposer names, or "oracle"')
    p.add_argument("--phrasings", nargs="+", default=["heldout", "paraphrase"])
    p.add_argument("--n", type=int, default=100)
    p.add_argument("--json", type=Path, default=None)
    args = p.parse_args(argv)
    netguard.install()
    rules = RuleExtractor()
    rows = []
    print(f"{'proposer':30s} {'phrasing':10s} {'recall':6s} {'lessons':>7s} {'decided':>8s} {'controls':>9s} "
          f"{'ctl FAIL':>8s} {'unsafe':>6s} {'exposed':>7s}")
    for name in args.models:
        if name == "oracle":
            proposer_for = OracleExtractor
        else:
            built = build("claude" if name.startswith("claude") else "openweight", model=name,
                          budget=Budget(None, 1.0))
            proposer_for = lambda _s, built=built: built  # noqa: E731
        for phrasing in args.phrasings:
            for recall in (False, True):
                total = {"lessons": 0, "exposed": 0}
                for world in worlds.suite(args.suite):
                    split = generate_split("test", args.n, phrasing, world=world)
                    half = len(split) // 2
                    lessons, exposed = teach(split[:half], proposer_for, recall)
                    out = measure(split[half:], lessons, lambda _s: rules)
                    total["lessons"] += len(lessons)
                    total["exposed"] += exposed
                    for key in ("claims", "decided", "controls", "controls_passed", "control_fails",
                                "defects", "defects_caught", "unsafe_passes"):
                        total[key] = total.get(key, 0) + out[key]
                row = {"proposer": name, "suite": args.suite, "phrasing": phrasing, "recall": recall, **total,
                       "decided_share": round(total["decided"] / total["claims"], 4)}
                rows.append(row)
                print(f"{name:30s} {phrasing:10s} {'yes' if recall else 'no':6s} {row['lessons']:7d} "
                      f"{row['decided_share']:8.1%} {row['controls_passed']:5d}/{row['controls']:<4d}"
                      f"{row['control_fails']:8d} {row['unsafe_passes']:6d} {row['exposed']:7d}", flush=True)
    if args.json:
        args.json.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
