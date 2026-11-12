"""teach-sim and the benchmark broken down by cause (event key), for the held-out-cause ablation.

    PROVEN_OPENAI_BASE_URL=http://127.0.0.1:8090/v1 \
    python training/by_cause.py --model <name> --phrasing heldout --n 220 [--json out.json]

It runs the same code as `python -m proven teach-sim` (`teachsim.teach` on the first half of
the test split, `teachsim.measure`'s scoring on the second half with the rules plus lessons)
and the same proposal cache, so against a cache the CLI already filled it sends nothing new.
The only addition is grouping: every claim is assigned to the cause its stated reason names,
and the causes are reported in two groups, the ones `build_dataset.ABLATION_KEYS` held out of
the ablation training set and the rest. It also reports, on the taught half, how many claims
the proposer did not extract at all and how many came back with no term that matched the
ledger, by group.

Loopback only: the network guard is installed, so a hosted endpoint is refused.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

from build_dataset import ABLATION_KEYS, PHRASE_TO_KEY  # noqa: E402
from proven import learned, netguard  # noqa: E402
from proven.budget import Budget  # noqa: E402
from proven.evaluate import score_claim  # noqa: E402
from proven.extract import RuleExtractor  # noqa: E402
from proven.extractors import build  # noqa: E402
from proven.report import run  # noqa: E402
from proven.synth import generate_split  # noqa: E402
from proven.teachsim import teach  # noqa: E402


def group_of(key: str) -> str:
    return "held-out causes" if key in ABLATION_KEYS else "other causes"


def analyse(model: str, phrasing: str, n: int) -> dict:
    netguard.install()
    proposer = build("openweight", model=model, budget=Budget(None, None))
    scenarios = generate_split("test", n, phrasing)
    half = len(scenarios) // 2
    pool, held = scenarios[:half], scenarios[half:]

    groups: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    # On the taught half: did the proposer extract the sentence, and did any of its terms match?
    for scenario in pool:
        report = run(scenario.explanation, scenario.ledger, extractor=proposer)
        by_quote = {c["claim"]["quote"]: c for c in report["claims"]}
        for label in scenario.labels:
            g = groups[group_of(PHRASE_TO_KEY[label.gold["reason_text"]])]
            g["taught_claims"] += 1
            result = by_quote.get(label.quote)
            if result is None:
                g["taught_not_extracted"] += 1
                continue
            matched = (result["reconstruction"].get("driver") or {}).get("matched", [])
            g["taught_with_matching_model_term"] += any(m["origin"] == "model" for m in matched)

    lessons = teach(pool, lambda _s: proposer)
    for entry in lessons:
        quote = entry["provenance"]["quote"]
        label = next(l for s in pool for l in s.labels if l.quote == quote)
        groups[group_of(PHRASE_TO_KEY[label.gold["reason_text"]])]["lessons"] += 1

    rules = RuleExtractor()
    for scenario in held:
        with learned.lexicon(lessons):
            report = run(scenario.explanation, scenario.ledger, extractor=rules)
        by_quote = {c["claim"]["quote"]: c for c in report["claims"]}
        for label in scenario.labels:
            g = groups[group_of(PHRASE_TO_KEY[label.gold["reason_text"]])]
            score = score_claim(label, by_quote.get(label.quote))
            g["held_claims"] += 1
            g["held_decided"] += score["verdict"] in ("PASS", "FAIL")
            if label.requirement == "PASS":
                g["held_control_fails"] += score["verdict"] == "FAIL"
            else:
                g["held_unsafe_passes"] += score["verdict"] == "PASS"

    out = {"model": model, "phrasing": phrasing, "n": n, "ablation_keys": list(ABLATION_KEYS),
           "lessons_total": len(lessons), "groups": {}}
    for name, g in sorted(groups.items()):
        g = dict(g)
        g["held_decided_share"] = round(g.get("held_decided", 0) / g["held_claims"], 4) \
            if g.get("held_claims") else None
        out["groups"][name] = g
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", required=True)
    parser.add_argument("--phrasing", default="heldout", choices=("heldout", "paraphrase"))
    parser.add_argument("--n", type=int, default=220)
    parser.add_argument("--json", default=None)
    args = parser.parse_args()
    result = analyse(args.model, args.phrasing, args.n)
    text = json.dumps(result, indent=1)
    print(text)
    if args.json:
        Path(args.json).write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
