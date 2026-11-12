"""Head-to-head on a world suite: one table from the JSON files `teach-sim --worlds --json` writes.

    python training/compare_worlds.py --results <dir> --suite unseen \
        --models oracle claude-sonnet-5-5 proven-qwen3b-worlds --against claude-sonnet-5-5

Files are `<dir>/<suite>-<model>-<phrasing>.json`. For each phrasing it prints the pooled
fully-taught row per model and, for every model against `--against`, the per-world record
(worlds won, tied, lost on decided share), the mean per-world difference and a 95% interval
for that mean from 10,000 bootstrap resamples of the worlds (seeded). The worlds are the
unit: closes within a world share its phrases, so they are not independent draws.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def load(results: Path, suite: str, model: str, phrasing: str) -> dict | None:
    path = results / f"{suite}-{model}-{phrasing}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--results", required=True, type=Path)
    p.add_argument("--suite", default="unseen")
    p.add_argument("--models", nargs="+", required=True)
    p.add_argument("--against", default=None)
    p.add_argument("--phrasings", nargs="+", default=["heldout", "paraphrase"])
    args = p.parse_args(argv)
    for phrasing in args.phrasings:
        data = {m: load(args.results, args.suite, m, phrasing) for m in args.models}
        print(f"\n{args.suite} / {phrasing}")
        print(f"{'model':28} lessons  decided  reward  controls passed  control FAIL  unsafe PASS  defects caught")
        for model, result in data.items():
            if result is None:
                print(f"{model:28} (not measured)")
                continue
            r = result["rows"][-1]
            print(f"{model:28} {r['lessons']:>7}  {r['decided_share']:>7.1%}  {r['mean_reward']:>6.3f}  "
                  f"{r['controls_passed']:>7}/{r['controls']:<7}  {r['control_fails']:>12}  "
                  f"{r['unsafe_passes']:>11}  {r['defects_caught']:>6}/{r['defects']}")
        base = data.get(args.against) if args.against else None
        if base is None:
            continue
        ref = {w["world"]: w["rows"][-1]["decided_share"] for w in base["worlds"]}
        for model, result in data.items():
            if result is None or model == args.against:
                continue
            diffs = [w["rows"][-1]["decided_share"] - ref[w["world"]] for w in result["worlds"]]
            rng = random.Random(0)
            means = sorted(sum(rng.choice(diffs) for _ in diffs) / len(diffs) for _ in range(10000))
            print(f"  {model} vs {args.against}: worlds won {sum(d > 0 for d in diffs)}, tied "
                  f"{sum(d == 0 for d in diffs)}, lost {sum(d < 0 for d in diffs)}; mean difference "
                  f"{sum(diffs) / len(diffs):+.1%} (95% interval {means[250]:+.1%} to {means[9750]:+.1%})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
