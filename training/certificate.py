"""A finite-sample bound on the two kill criteria, from the saved world-suite results.

    python training/certificate.py --results <dir> --suites unseen sealed \
        --models claude-sonnet-5-5 oracle

"Zero unsafe PASS" is an observation about the claims that were scored. This script turns
it into a statement about claims that were not: the exact one-sided Clopper-Pearson upper
bound (Clopper and Pearson 1934) on the true rate, at confidence 1 - alpha. With k breaches
in n trials the bound is the largest rate p for which seeing k or fewer is still at least
alpha likely; for k = 0 it is 1 - alpha**(1/n), about 3/n at 95% (the "rule of three").

Two units are reported, because they answer different questions:

  claim    every false claim (for unsafe PASS) or true claim (for control FAIL) scored after
           full teaching is one trial. Tight, but claims inside a world share its phrases and
           books, so they are not independent draws and the bound is optimistic.
  world    a world is one trial, breached if any of its claims is. Worlds are authored
           independently, so this bound holds without the independence assumption, and is
           wide because there are few worlds.

The truth lies between the two. Phrasings of one suite reword the same closes, so they are
bounded separately and never added together. Reads JSON only; sends nothing.
"""
from __future__ import annotations

import argparse
import json
from math import comb
from pathlib import Path


def upper_bound(breaches: int, trials: int, alpha: float = 0.05) -> float:
    """Exact one-sided upper confidence bound on a binomial rate."""
    if trials <= 0:
        return 1.0
    if breaches >= trials:
        return 1.0
    if breaches == 0:
        return 1.0 - alpha ** (1.0 / trials)

    def at_most(p: float) -> float:
        return sum(comb(trials, i) * p ** i * (1.0 - p) ** (trials - i) for i in range(breaches + 1))

    low, high = breaches / trials, 1.0
    for _ in range(60):
        mid = (low + high) / 2.0
        low, high = (mid, high) if at_most(mid) > alpha else (low, mid)
    return high


def tally(files: list[Path]) -> dict[str, list[tuple[int, int]]]:
    """Per world, (breaches, trials) after full teaching, for both criteria."""
    out: dict[str, list[tuple[int, int]]] = {"unsafe PASS": [], "control FAIL": []}
    for file in files:
        for world in json.loads(file.read_text(encoding="utf-8"))["worlds"]:
            last = world["rows"][-1]
            out["unsafe PASS"].append((last["unsafe_passes"], last["defects"]))
            out["control FAIL"].append((last["control_fails"], last["controls"]))
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--results", required=True, type=Path)
    p.add_argument("--suites", nargs="+", default=["unseen", "sealed"])
    p.add_argument("--models", nargs="+", required=True)
    p.add_argument("--phrasings", nargs="+", default=["heldout", "paraphrase"])
    p.add_argument("--alpha", type=float, default=0.05)
    args = p.parse_args(argv)
    level = f"{1 - args.alpha:.0%}"
    print(f"{'proposer':22s} {'phrasing':10s} {'criterion':13s} {'breaches':>8s} {'claims':>7s} "
          f"{'rate <':>8s} {'worlds':>7s} {'rate <':>8s}   ({level} one-sided, exact)")
    for model in args.models:
        for phrasing in args.phrasings:
            files = [f for s in args.suites if (f := args.results / f"{s}-{model}-{phrasing}.json").is_file()]
            if not files:
                print(f"{model:22s} {phrasing:10s} no results")
                continue
            for criterion, rows in tally(files).items():
                breaches, trials = sum(b for b, _ in rows), sum(n for _, n in rows)
                bad_worlds = sum(1 for b, _ in rows if b)
                print(f"{model:22s} {phrasing:10s} {criterion:13s} {breaches:8d} {trials:7d} "
                      f"{upper_bound(breaches, trials, args.alpha):8.2%} {len(rows):7d} "
                      f"{upper_bound(bad_worlds, len(rows), args.alpha):8.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
