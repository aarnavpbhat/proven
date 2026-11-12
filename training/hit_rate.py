"""How often a proposer's blind search terms find a true cause in the books.

    python training/hit_rate.py --suite dev --models proven-qwen3b-worlds claude-sonnet-5-5

For every true explanation in the taught half of each world (the closes a proposer is
shown), the checker's own report says what became of the proposal:

  found      the terms matched the cause's transactions (`SUPPORT_RESTS_ON_MODEL_TERMS`:
             a reviewer could confirm them as a lesson);
  routine    terms matched something in the account, but not enough to carry the movement;
  nothing    no term matched;
  other      any other outcome (a FAIL here would be a kill-criterion breach);
  missed     no proposal for the sentence.

`found` is the quantity teaching depends on, and it needs no teaching run to measure, so
it is what checkpoints and decoding policies are compared on (dev worlds only). Answers
come from the cache; nothing is sent anywhere.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from proven import netguard, worlds  # noqa: E402
from proven.budget import Budget  # noqa: E402
from proven.extractors import build  # noqa: E402
from proven.report import run  # noqa: E402
from proven.synth import generate_split  # noqa: E402

FOUND, ROUTINE, NOTHING = ("SUPPORT_RESTS_ON_MODEL_TERMS", "REASON_FOUND_ONLY_BY_MODEL_TERMS",
                           "REASON_NOT_FOUND")


def outcomes(proposer, suite: str, phrasing: str, n: int = 100) -> dict[str, int]:
    out = {"claims": 0, "found": 0, "routine": 0, "nothing": 0, "other": 0, "missed": 0, "terms": 0}
    for world in worlds.suite(suite):
        split = generate_split("test", n, phrasing, world=world)
        for scenario in split[:len(split) // 2]:
            report = run(scenario.explanation, scenario.ledger, extractor=proposer)
            by_quote = {c["claim"]["quote"]: c for c in report["claims"]}
            for label in scenario.labels:
                if label.requirement != "PASS":
                    continue
                out["claims"] += 1
                result = by_quote.get(label.quote)
                if result is None:
                    out["missed"] += 1
                    continue
                codes = {f["code"] for f in result["findings"]}
                out["terms"] += len(result["claim"].get("terms") or [])
                kind = ("found" if result["verdict"] == "REVIEW" and FOUND in codes else
                        "routine" if result["verdict"] == "REVIEW" and ROUTINE in codes else
                        "nothing" if result["verdict"] == "REVIEW" and NOTHING in codes else "other")
                out[kind] += 1
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--suite", default="dev")
    p.add_argument("--models", nargs="+", required=True)
    p.add_argument("--phrasings", nargs="+", default=["heldout", "paraphrase"])
    p.add_argument("--n", type=int, default=100)
    args = p.parse_args(argv)
    netguard.install()
    print(f"{'model':34s} {'phrasing':10s} {'claims':>6s} {'found':>7s} {'routine':>8s} {'nothing':>8s} "
          f"{'other':>6s} {'missed':>7s}")
    for name in args.models:
        kind = "claude" if name.startswith("claude") else "openweight"
        proposer = build(kind, model=name, budget=Budget(None, 1.0))
        for phrasing in args.phrasings:
            try:
                o = outcomes(proposer, args.suite, phrasing, args.n)
            except Exception as error:  # noqa: BLE001 - an uncached proposer has no answers to read
                print(f"{name:34s} {phrasing:10s} not cached ({type(error).__name__})")
                continue
            share = o["found"] / o["claims"] if o["claims"] else 0.0
            print(f"{name:34s} {phrasing:10s} {o['claims']:6d} {share:7.1%} {o['routine']:8d} "
                  f"{o['nothing']:8d} {o['other']:6d} {o['missed']:7d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
