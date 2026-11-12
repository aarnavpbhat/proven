"""What a wider list of search terms costs: wrong claims a reviewer is shown as supported.

    python training/breadth_cost.py --suite dev --models <cached names> [--phrasings heldout]

More search terms find more true causes, and they also match more lines that are not the
cause. Nothing passes on model terms alone, so the cost is not an unsafe PASS: it is a
wrong claim that reaches the reviewer marked "supported by terms a model proposed"
(`SUPPORT_RESTS_ON_MODEL_TERMS`), where a reviewer who confirmed everything would teach a
false lesson. For every claim of the taught half of each world, untaught, this prints

  true found     true claims whose terms matched the cause (what teaching needs);
  wrong shown    claims that must not pass, shown as supported (what breadth costs);
  terms          the mean number of terms sent per true claim.

Answers come from the cache; nothing is sent anywhere.
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

FOUND = "SUPPORT_RESTS_ON_MODEL_TERMS"


def cost(proposer, suite: str, phrasing: str, n: int = 100) -> dict[str, int]:
    out = {"true": 0, "found": 0, "wrong": 0, "shown": 0, "terms": 0}
    for world in worlds.suite(suite):
        split = generate_split("test", n, phrasing, world=world)
        for scenario in split[:len(split) // 2]:
            report = run(scenario.explanation, scenario.ledger, extractor=proposer)
            by_quote = {c["claim"]["quote"]: c for c in report["claims"]}
            for label in scenario.labels:
                result = by_quote.get(label.quote)
                supported = (result is not None and result["verdict"] == "REVIEW"
                             and FOUND in {f["code"] for f in result["findings"]})
                if label.requirement == "PASS":
                    out["true"] += 1
                    out["found"] += supported
                    out["terms"] += len(result["claim"].get("terms") or []) if result else 0
                else:
                    out["wrong"] += 1
                    out["shown"] += supported
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--suite", default="dev")
    p.add_argument("--models", nargs="+", required=True)
    p.add_argument("--phrasings", nargs="+", default=["heldout"])
    p.add_argument("--n", type=int, default=100)
    args = p.parse_args(argv)
    netguard.install()
    print(f"{'model':34s} {'phrasing':10s} {'true found':>16s} {'wrong shown':>16s} {'terms':>6s}")
    for name in args.models:
        kind = "claude" if name.startswith("claude") else "openweight"
        proposer = build(kind, model=name, budget=Budget(None, 1.0))
        for phrasing in args.phrasings:
            try:
                o = cost(proposer, args.suite, phrasing, args.n)
            except Exception as error:  # noqa: BLE001 - an uncached proposer has no answers to read
                print(f"{name:34s} {phrasing:10s} not cached ({type(error).__name__})")
                continue
            print(f"{name:34s} {phrasing:10s} {o['found']:4d}/{o['true']:<4d} {o['found'] / max(1, o['true']):6.1%} "
                  f"{o['shown']:4d}/{o['wrong']:<4d} {o['shown'] / max(1, o['wrong']):6.1%} "
                  f"{o['terms'] / max(1, o['true']):6.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
