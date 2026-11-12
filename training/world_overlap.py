"""What the measured worlds share with the training worlds: an audit, not a filter.

    python training/world_overlap.py --train training/worlds/train training/worlds/dev [--suite unseen]

For every cause of every measured world it reports whether its vendor, its memo lines, its
phrases and each of its distinguishing memo words (the terms a proposer has to supply) also
occur in the training worlds or in the default world. Vendors, memo lines and phrases
should not recur at all. Single bookkeeping words ("repair", "overtime", "annual") will: the
point of training on many worlds is to learn which words books use, so the audit also says
how many measured terms were never a target term in training, and `--json` lists them so a
result can be split by it.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from proven import worlds  # noqa: E402
from proven.synth import DEFAULT, cause_terms  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--train", nargs="+", required=True, type=Path)
    p.add_argument("--suite", default="unseen")
    p.add_argument("--json", type=Path, default=None)
    args = p.parse_args(argv)
    training = [worlds.load(f, role="train") for folder in args.train for f in sorted(folder.glob("*.json"))]
    training.append(DEFAULT)
    seen = {"terms": set(), "vendors": set(), "phrases": set(), "memos": set(), "industries": set()}
    for world in training:
        vocab = worlds.vocabulary(world)
        for key in ("terms", "vendors", "phrases"):
            seen[key] |= vocab[key]
        seen["memos"] |= {m.lower() for spec in world.specs for e in spec.events for m in e.memos}
    out = {"training_worlds": len(training), "worlds": {}}
    total = {"causes": 0, "terms": 0, "terms_new": 0, "causes_all_terms_new": 0,
             "causes_no_term_new": 0, "vendors_shared": 0, "memos_shared": 0, "phrases_shared": 0}
    for world in worlds.suite(args.suite):
        vocab = worlds.vocabulary(world)
        causes = {}
        for spec in world.specs:
            for event in spec.events:
                terms = cause_terms(spec, event)
                new = [t for t in terms if t not in seen["terms"]]
                causes[event.key] = {"terms": terms, "never_a_training_target": new}
                total["causes"] += 1
                total["terms"] += len(terms)
                total["terms_new"] += len(new)
                total["causes_all_terms_new"] += len(new) == len(terms)
                total["causes_no_term_new"] += not new
                total["memos_shared"] += sum(m.lower() in seen["memos"] for m in event.memos)
        total["vendors_shared"] += len(vocab["vendors"] & seen["vendors"])
        total["phrases_shared"] += len(vocab["phrases"] & seen["phrases"])
        out["worlds"][world.name] = {"causes": causes,
                                     "vendors_shared": sorted(vocab["vendors"] & seen["vendors"]),
                                     "phrases_shared": sorted(vocab["phrases"] & seen["phrases"])}
    out["total"] = total
    print(json.dumps(total, indent=1))
    if args.json:
        args.json.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
