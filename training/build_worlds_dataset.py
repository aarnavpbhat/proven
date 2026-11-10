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

TARGETS (`--teacher DIR`). The generator's gold search terms are what a cause really left in
the books, vendor names included, and nothing in a request predicts a vendor's name. With
`--teacher`, each claim's terms are rebuilt from three sources, in this order, up to
`--max-terms`:
  1. the blind teacher's guesses for that phrase (`teacher_terms.py`) that the cause's own
     vendor-and-memo lines really contain: guessable and true;
  2. the gold memo words that the cause memos of at least `--common-min` training worlds
     use ("retrofit", "overtime", "pilot": bookkeeping vocabulary a proposer can learn a
     prior over), never a word found only in a vendor's name;
  3. the teacher's other guesses, as filler.
A teacher guess that matches the account's routine lines, or restates the account, is dropped.
A gold word one world alone uses ("westgate", "tablecloth") is left out unless fewer than
three terms would remain: no request predicts it, and training on it teaches invention.
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
from proven.claims import term_pattern  # noqa: E402
from proven.llm import SYSTEM, payload, restates_account  # noqa: E402
from proven.synth import DEFAULT, Scenario, _TOKEN, generate, seeds  # noqa: E402

FIRST_SEED_INDEX = 4000        # clear of build_dataset.py (first ~1,100) and rl.py (from 2,000)


def tokens(text: str) -> set[str]:
    return {t.strip("-'") for t in _TOKEN.findall(text.lower())}


def common_words(train_worlds: list, at_least: int) -> set[str]:
    """Memo words that the causes of `at_least` or more training worlds use."""
    seen: dict[str, int] = {}
    for world in train_worlds:
        words = set().union(*(tokens(memo) for spec in world.specs for event in spec.events
                              for memo in event.memos))
        for word in words:
            seen[word] = seen.get(word, 0) + 1
    return {word for word, count in seen.items() if count >= at_least}


def cause_index(world) -> dict[str, tuple]:
    """Every phrase of a world, lower-cased -> (its account spec, its cause)."""
    out = {}
    for spec in world.specs:
        for event in spec.events:
            for bank in (event.phrases, world.heldout[event.key], world.paraphrase_train[event.key],
                         world.paraphrase_test[event.key]):
                for phrase in bank:
                    out[phrase.lower()] = (spec, event)
    return out


def targets(spec, event, gold: list[str], guesses: list[str], ledger, max_terms: int,
            common: set[str] | None = None) -> tuple[list[str], int]:
    """(the search terms to train on, how many of them are teacher guesses the books contain)."""
    lines = [f"{event.vendor} {memo}".lower() for memo in event.memos]
    routine = [f"{r.vendor} {r.memo}".lower() for r in spec.recurring]
    memo_words = set().union(*(tokens(m) for m in event.memos))
    vendor_only = tokens(event.vendor) - memo_words
    hits, misses = [], []
    for guess in guesses:
        if restates_account(guess, spec.name, ledger) or tokens(guess) & vendor_only:
            continue
        pattern = term_pattern(guess)
        if any(pattern.search(line) for line in routine):
            continue
        (hits if any(pattern.search(line) for line in lines) else misses).append(guess)
    true = [w for w in gold if w not in vendor_only]
    out = list(hits)
    out += [w for w in true if w not in out and (common is None or w in common)]
    out += [m for m in misses if m not in out]
    if len(out) < 3:
        out += [w for w in true if w not in out]
    return out[:max_terms], len(hits[:max_terms])


class Relabel:
    """Rewrites the gold search terms of a world's closes (see TARGETS above)."""

    def __init__(self, teacher_dir: Path | None, max_terms: int, common: set[str] | None = None):
        self.dir, self.max_terms, self.common = teacher_dir, max_terms, common
        self.claims = self.with_guess = self.with_hit = 0
        self._index: dict[str, dict] = {}
        self._teacher: dict[str, dict] = {}

    def __call__(self, scenario: Scenario, world, slug: str) -> dict:
        if scenario.split != "train":
            raise ValueError(f"refusing to build a training row from {scenario.split} seed {scenario.seed}")
        if self.dir is None:
            return scenario.to_chat()
        if slug not in self._index:
            self._index[slug] = cause_index(world)
            file = self.dir / f"{slug}.json"
            self._teacher[slug] = json.loads(file.read_text(encoding="utf-8")) if file.exists() else {}
        claims = []
        for claim in scenario.gold_claims():
            claim = dict(claim)
            found = self._index[slug].get(claim["reason_text"].lower())
            if found and claim["search_terms"]:
                spec, event = found
                guesses = self._teacher[slug].get(f"{spec.name}\t{claim['reason_text']}", [])
                claim["search_terms"], hit = targets(spec, event, claim["search_terms"], guesses,
                                                     scenario.ledger, self.max_terms, self.common)
                self.claims += 1
                self.with_guess += bool(guesses)
                self.with_hit += bool(hit)
            claims.append(claim)
        return {"messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": payload(scenario.explanation, scenario.ledger)},
            {"role": "assistant", "content": json.dumps({"claims": claims}, ensure_ascii=False)}]}


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
    p.add_argument("--teacher", type=Path, default=None, help="teacher_terms.py output directory")
    p.add_argument("--max-terms", type=int, default=8)
    p.add_argument("--common-min", type=int, default=3,
                   help="a gold memo word is kept when this many training worlds use it (0: keep all)")
    args = p.parse_args(argv)

    train_worlds, dev_worlds = load_all(args.worlds), load_all(args.dev)
    common = common_words(train_worlds, args.common_min) if args.common_min else None
    row = Relabel(args.teacher, args.max_terms, common)
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
            rows.append(row(scenario, world, world.name))
            used.append({"seed": seed, "phrasing": phrasing})
        manifest["worlds"][world.name] = used
    for i, seed in enumerate(train_seeds[args.per_world:args.per_world + args.default]):
        phrasing = "seen" if i % 2 == 0 else "paraphrase"
        scenario = generate(seed, phrasing=phrasing)
        if not clean(scenario):                # "the data migration" is a measured world's phrase too
            dropped += 1
            continue
        rows.append(row(scenario, DEFAULT, "default"))
        manifest["default"].append({"seed": seed, "phrasing": phrasing})
    random.Random(args.seed).shuffle(rows)
    valid: list[dict] = []
    for i, seed in enumerate(train_seeds[-args.valid:]):
        world = dev_worlds[i % len(dev_worlds)]
        phrasing = "seen" if (i // len(dev_worlds)) % 4 == 0 else "paraphrase"   # every world gets both
        valid.append(row(generate(seed, phrasing=phrasing, world=world), world, world.name))
        manifest["valid"].append({"world": world.name, "seed": seed, "phrasing": phrasing})
    args.out.mkdir(parents=True, exist_ok=True)
    for name, data in (("train", rows), ("valid", valid)):
        with (args.out / f"{name}.jsonl").open("w", encoding="utf-8") as handle:
            for item in data:
                handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    causes = sum(len(w.specs) * 2 for w in train_worlds)
    if args.teacher:
        print(f"{row.claims} claims with a reason relabelled: {row.with_guess} had teacher guesses, "
              f"{row.with_hit} had at least one guess the cause's own lines contain")
    print(f"dropped {dropped} closes that used a measured world's phrase word for word")
    print(f"wrote {len(rows)} train rows ({len(train_worlds)} worlds, {causes} causes, "
          f"{len(manifest['default'])} default-world rows) and {len(valid)} valid rows "
          f"({len(dev_worlds)} dev worlds) to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
