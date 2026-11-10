"""Build a LoRA training set that spans many worlds, so the bookkeeping words cannot be memorised.

    python training/build_worlds_dataset.py --out <dir> --worlds training/worlds/train \
        --dev training/worlds/dev [--per-world 40 --default 400 --valid 80]

`build_dataset.py` draws every row from the default world, and a proposer trained on it
learns which words that world's books use for each of its eighteen causes (the ablation in
docs/finetune.md shows it). Here each row comes from one of many authored worlds, each with
its own chart, vendors, memos and causes, so the only thing constant across rows is the
task: copy the sentence and its figures, name the account from the chart given, and propose
the words a bookkeeper would plausibly have written for the reason stated.

WHAT GOES IN
  * `--per-world` closes from every world file under `--worlds`, train seeds only, a quarter
    in the plain ("seen") tier and the rest oblique ("paraphrase"; a training world offers
    every oblique phrase to the train split);
  * `--default` closes from the default world, built exactly as `build_dataset.py` builds them
    (train seeds, `seen` and train-split `paraphrase`), so results there are not given up;
  * validation rows come from the `--dev` worlds, which contribute nothing to train.jsonl.

WHAT STAYS OUT. The builder refuses a `--worlds` or `--dev` path inside
`proven/examples/worlds/` (the measured suites). It reads the measured suites for one
purpose only: a close is dropped if any sentence's stated reason is word-for-word a phrase
some measured world uses (two authors do sometimes write "the emergency repairs"), and the
count is printed. `world_overlap.py` reports what vocabulary the measured worlds
nevertheless share with these.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from proven import worlds  # noqa: E402
from proven.synth import Scenario, generate, seeds  # noqa: E402

FIRST_SEED_INDEX = 4000        # clear of build_dataset.py (first ~1,100) and rl.py (from 2,000)


def row(scenario: Scenario) -> dict:
    if scenario.split != "train":
        raise ValueError(f"refusing to build a training row from {scenario.split} seed {scenario.seed}")
    return scenario.to_chat()


def load_all(folder: Path) -> list:
    if worlds.HERE.resolve() in folder.resolve().parents or folder.resolve() == worlds.HERE.resolve():
        raise SystemExit(f"{folder} is a measured suite; it may not be trained on")
    return [worlds.load(f, role="train") for f in sorted(folder.glob("*.json"))]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--worlds", required=True, type=Path)
    p.add_argument("--dev", required=True, type=Path)
    p.add_argument("--per-world", type=int, default=40)
    p.add_argument("--default", type=int, default=400)
    p.add_argument("--valid", type=int, default=80)
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args(argv)

    train_worlds, dev_worlds = load_all(args.worlds), load_all(args.dev)
    measured = {phrase for folder in sorted(worlds.HERE.iterdir()) if folder.is_dir()
                for world in worlds.suite(folder.name) for phrase in worlds.vocabulary(world)["phrases"]}
    dropped = 0

    def clean(scenario: Scenario) -> bool:
        return not any(label.gold["reason_text"].lower() in measured for label in scenario.labels)

    train_seeds = seeds("train", FIRST_SEED_INDEX + args.per_world + args.default + args.valid)[FIRST_SEED_INDEX:]
    rows: list[dict] = []
    manifest: dict = {"split": "train", "worlds": {}, "default": [], "valid": []}
    for world in train_worlds:
        used = []
        for i, seed in enumerate(train_seeds[:args.per_world]):
            phrasing = "seen" if i % 4 == 0 else "paraphrase"
            scenario = generate(seed, phrasing=phrasing, world=world)
            if not clean(scenario):
                dropped += 1
                continue
            rows.append(row(scenario))
            used.append({"seed": seed, "phrasing": phrasing})
        manifest["worlds"][world.name] = used
    for i, seed in enumerate(train_seeds[args.per_world:args.per_world + args.default]):
        phrasing = "seen" if i % 2 == 0 else "paraphrase"
        rows.append(row(generate(seed, phrasing=phrasing)))
        manifest["default"].append({"seed": seed, "phrasing": phrasing})
    random.Random(args.seed).shuffle(rows)
    valid: list[dict] = []
    for i, seed in enumerate(train_seeds[-args.valid:]):
        world = dev_worlds[i % len(dev_worlds)]
        phrasing = "seen" if i % 4 == 0 else "paraphrase"
        valid.append(row(generate(seed, phrasing=phrasing, world=world)))
        manifest["valid"].append({"world": world.name, "seed": seed, "phrasing": phrasing})
    args.out.mkdir(parents=True, exist_ok=True)
    for name, data in (("train", rows), ("valid", valid)):
        with (args.out / f"{name}.jsonl").open("w", encoding="utf-8") as handle:
            for item in data:
                handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    causes = sum(len(w.specs) * 2 for w in train_worlds)
    print(f"dropped {dropped} closes that used a measured world's phrase word for word")
    print(f"wrote {len(rows)} train rows ({len(train_worlds)} worlds, {causes} causes, "
          f"{len(manifest['default'])} default-world rows) and {len(valid)} valid rows "
          f"({len(dev_worlds)} dev worlds) to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
