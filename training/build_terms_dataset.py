"""Build a LoRA training set for the terms-only task: one stated reason in, search terms out.

    python training/build_terms_dataset.py --out <dir> --worlds training/worlds/train \
        --dev training/worlds/dev --teacher <teacher_terms.py output>

WHY. A proposer does two different jobs. Copying the sentence, the account and the figures
is a format task a 3B model does perfectly (docs/finetune.md, section 7). Guessing, blind,
the words a bookkeeper wrote is a knowledge task, and it is where every local model loses.
`build_worlds_dataset.py` trains both at once on whole closes (about a thousand tokens a
row, two or three reasons each). This builder trains the second job alone: each row is the
teacher's own request (`teacher_terms.BRIEF`: the account names and ONE stated reason) and
the answer is that reason's rebuilt targets (`build_worlds_dataset.targets`: the teacher's
guesses that the cause's own lines contain, then common bookkeeping words, then filler).
Rows are about 300 tokens, so every labelled phrase of every training world fits in one
epoch, and a base model too large to train on whole closes can be trained on these.

WHAT STAYS OUT. The same rules as `build_worlds_dataset.py`: measured suites are refused as
`--worlds` or `--dev`, a phrase some measured world uses word for word is dropped, the dev
worlds give validation rows only, and no transaction is ever in a prompt.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
for folder in (ROOT, HERE):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

from build_worlds_dataset import common_words, load_all, targets  # noqa: E402
from teacher_terms import BRIEF, SYSTEM  # noqa: E402
from proven import worlds  # noqa: E402
from proven.synth import cause_terms  # noqa: E402


def rows_of(world, teacher: dict, common: set[str] | None, measured: set[str], max_terms: int,
            oblique_only: bool = False) -> tuple[list[dict], dict[str, int]]:
    """Every usable (account, phrase) of one world as a chat row, and what was counted."""
    chart = "\n".join(f"- {spec.name}" for spec in world.specs)
    ledger = SimpleNamespace(accounts=world.chart)       # all `restates_account` reads
    rows, stats = [], {"rows": 0, "hit": 0, "dropped": 0, "thin": 0}
    for spec in world.specs:
        for event in spec.events:
            gold = cause_terms(spec, event)
            oblique = list(world.paraphrase_train[event.key])
            plain = [] if oblique_only else [*event.phrases, *world.heldout.get(event.key, ())]
            for phrase in dict.fromkeys([*oblique, *plain]):
                if phrase.lower() in measured:
                    stats["dropped"] += 1
                    continue
                guesses = teacher.get(f"{spec.name}\t{phrase}", [])
                terms, hit = targets(spec, event, gold, guesses, ledger, max_terms, common)
                if len(terms) < 3:
                    stats["thin"] += 1
                    continue
                rows.append({"messages": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": BRIEF.format(chart=chart, items=f'1. [{spec.name}] "{phrase}"')},
                    {"role": "assistant", "content": json.dumps({"1": terms}, ensure_ascii=False)}]})
                stats["rows"] += 1
                stats["hit"] += bool(hit)
    return rows, stats


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--worlds", required=True, type=Path)
    p.add_argument("--dev", required=True, type=Path)
    p.add_argument("--teacher", required=True, type=Path, help="teacher_terms.py output directory")
    p.add_argument("--valid", type=int, default=200)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--max-terms", type=int, default=8)
    p.add_argument("--common-min", type=int, default=3)
    args = p.parse_args(argv)

    train_worlds, dev_worlds = load_all(args.worlds), load_all(args.dev)
    common = common_words(train_worlds, args.common_min) if args.common_min else None
    measured = {phrase for folder in sorted(worlds.HERE.iterdir()) if folder.is_dir()
                for world in worlds.suite(folder.name) for phrase in worlds.vocabulary(world)["phrases"]}

    def labels(world) -> dict:
        file = args.teacher / f"{world.name}.json"
        return json.loads(file.read_text(encoding="utf-8")) if file.exists() else {}

    total = {"rows": 0, "hit": 0, "dropped": 0, "thin": 0}
    train: list[dict] = []
    for world in train_worlds:
        rows, stats = rows_of(world, labels(world), common, measured, args.max_terms)
        train += rows
        for key, value in stats.items():
            total[key] += value
    valid: list[dict] = []
    for world in dev_worlds:                 # oblique phrases only: the dev heldout tier is measured
        valid += rows_of(world, labels(world), common, measured, args.max_terms, oblique_only=True)[0]
    rng = random.Random(args.seed)
    rng.shuffle(train)
    rng.shuffle(valid)
    valid = valid[:args.valid]
    args.out.mkdir(parents=True, exist_ok=True)
    for name, data in (("train", train), ("valid", valid)):
        with (args.out / f"{name}.jsonl").open("w", encoding="utf-8") as handle:
            for item in data:
                handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"wrote {len(train)} train rows from {len(train_worlds)} worlds ({total['hit']} with a teacher "
          f"guess the cause's own lines contain) and {len(valid)} valid rows from {len(dev_worlds)} dev "
          f"worlds to {args.out}; dropped {total['dropped']} phrases a measured world uses and "
          f"{total['thin']} with fewer than three terms")
    return 0


if __name__ == "__main__":
    sys.exit(main())
