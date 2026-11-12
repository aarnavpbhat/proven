"""Ask a proposer about every close of a world suite, several at a time, so that a later
`python -m proven teach-sim --worlds <suite>` is answered from the proposal cache.

    python training/warm_worlds.py --extractor openweight --model <name> --suite unseen \
        --phrasings heldout paraphrase --n 100 --workers 4 [--allow-network --usd-budget 10]
"""
from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from proven import env, netguard, worlds  # noqa: E402
from proven.budget import Budget, BudgetExceeded  # noqa: E402
from proven.extractors import build  # noqa: E402
from proven.synth import generate_split  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--extractor", required=True)
    p.add_argument("--model", default=None)
    p.add_argument("--suite", default="unseen")
    p.add_argument("--phrasings", nargs="+", default=["heldout", "paraphrase"])
    p.add_argument("--n", type=int, default=100)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--allow-network", action="store_true")
    p.add_argument("--usd-budget", type=float, default=None)
    p.add_argument("--taught-only", action="store_true",
                   help="only the first half of each split: the closes teach-sim shows a proposer")
    args = p.parse_args(argv)
    env.load()
    netguard.allow_network() if args.allow_network else netguard.install()
    proposer = build(args.extractor, model=args.model, budget=Budget(None, args.usd_budget))
    closes = []
    for world in worlds.suite(args.suite):
        for phrasing in args.phrasings:
            split = generate_split("test", args.n, phrasing, world=world)
            closes += split[:len(split) // 2] if args.taught_only else split
    start, failed = time.time(), 0

    def one(scenario) -> int:
        try:
            proposer.propose(scenario.explanation, scenario.ledger)
            return 0
        except BudgetExceeded:
            raise
        except Exception as error:  # noqa: BLE001 - count it; teach-sim will ask again
            print(f"{scenario.scenario_id}: {type(error).__name__}: {str(error)[:120]}", file=sys.stderr)
            return 1

    with ThreadPoolExecutor(args.workers) as pool:
        failed = sum(pool.map(one, closes))
    budget = getattr(proposer, "budget", None)
    print(f"{len(closes)} closes, {failed} failed, {round(time.time() - start)}s"
          + (f", {budget.calls} requests, ${budget.usd:.2f}" if budget is not None else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
