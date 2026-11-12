"""Build the LoRA training set for a local proposer, from the TRAIN split only.

    python training/build_dataset.py --out <dir> [--seen 500 --paraphrase 500 --valid 60]
                                     [--exclude-keys litigation,migration,offsite,d_and_o]

Writes `<dir>/train.jsonl`, `<dir>/valid.jsonl` (the `{"messages": [...]}` chat format
`mlx_lm.lora` reads) and `<dir>/manifest.json` (every seed and phrasing used, so the
leakage test can regenerate each row and check it).

WHAT GOES IN

  * seeds: only `split_of(seed) == "train"` (seed % 5 != 0). Test seeds are never generated.
  * phrasings: `seen` (the lexicon phrases) and `paraphrase`, which on the train split draws
    only from `PARAPHRASE_TRAIN`. `HELDOUT` and `PARAPHRASE_TEST` are never drawn.
  * the prompt is exactly what `proven/openweight.py` sends: the system message is
    `proven.llm.SYSTEM` and the user message is `proven.llm.payload(text, ledger)`, the two
    names openweight imports. `test_leakage.py` checks this against a captured request body.
  * the target is the generator's gold proposal list (`Scenario.gold_claims()`) as JSON.

ABLATION

`--exclude-keys` drops every close in which any sentence is about one of the listed causes
(event keys), so a model trained on the result has never seen those causes' phrases or the
ledger vocabulary their gold terms carry. The validation rows obey the same exclusion.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from proven.llm import SYSTEM, payload  # noqa: E402  (the names openweight.py sends)
from proven.synth import (HELDOUT, PARAPHRASE_TEST, PARAPHRASE_TRAIN, WORLD,  # noqa: E402
                          Scenario, generate, seeds, split_of)

TRAIN_PHRASINGS = ("seen", "paraphrase")
#: Fixed before any ablation run was measured: 4 of 18 causes, in 4 different accounts, two
#: billed by a recurring vendor (migration, d_and_o) and two by a vendor of their own.
ABLATION_KEYS = ("litigation", "migration", "offsite", "d_and_o")


def _phrase_index() -> dict[str, str]:
    index: dict[str, str] = {}
    for spec in WORLD:
        for event in spec.events:
            for phrase in (event.phrases + HELDOUT[event.key] + PARAPHRASE_TRAIN[event.key]
                           + PARAPHRASE_TEST[event.key]):
                index[phrase] = event.key
    return index


PHRASE_TO_KEY = _phrase_index()


def cause_keys(scenario: Scenario) -> list[str]:
    """The event key each sentence of the close is about, from its stated reason."""
    return [PHRASE_TO_KEY[label.gold["reason_text"]] for label in scenario.labels]


def example(scenario: Scenario) -> dict:
    """One chat example: the request openweight.py sends, and the gold JSON reply."""
    if scenario.split != "train":
        raise ValueError(f"refusing to build a training row from {scenario.split} seed {scenario.seed}")
    row = {"messages": [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": payload(scenario.explanation, scenario.ledger)},
        {"role": "assistant", "content": json.dumps({"claims": scenario.gold_claims()},
                                                    ensure_ascii=False)},
    ]}
    assert row == scenario.to_chat(), "the generator's to_chat() and this builder disagree"
    return row


def plan(n_seen: int, n_paraphrase: int, n_valid: int,
         exclude: tuple[str, ...] = ()) -> dict[str, list[tuple[int, str]]]:
    """(seed, phrasing) pairs for each file. Distinct train seeds throughout: the first
    `n_seen` kept seeds get `seen`, the next `n_paraphrase` get `paraphrase`, then `n_valid`
    alternate between the two for validation."""
    wanted = [("train", "seen")] * n_seen + [("train", "paraphrase")] * n_paraphrase \
        + [("valid", TRAIN_PHRASINGS[i % 2]) for i in range(n_valid)]
    out: dict[str, list[tuple[int, str]]] = {"train": [], "valid": []}
    candidates = iter(seeds("train", 10 ** 6))
    for name, phrasing in wanted:
        while True:
            seed = next(candidates)
            assert split_of(seed) == "train"
            if exclude and set(cause_keys(generate(seed, phrasing=phrasing))) & set(exclude):
                continue
            out[name].append((seed, phrasing))
            break
    return out


def build(out_dir: Path, n_seen: int, n_paraphrase: int, n_valid: int,
          exclude: tuple[str, ...] = ()) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    chosen = plan(n_seen, n_paraphrase, n_valid, exclude)
    for name, pairs in chosen.items():
        with (out_dir / f"{name}.jsonl").open("w", encoding="utf-8") as handle:
            for seed, phrasing in pairs:
                handle.write(json.dumps(example(generate(seed, phrasing=phrasing)),
                                        ensure_ascii=False) + "\n")
    manifest = {"split": "train", "phrasings": list(TRAIN_PHRASINGS),
                "exclude_keys": list(exclude),
                "files": {name: [{"seed": s, "phrasing": p} for s, p in pairs]
                          for name, pairs in chosen.items()}}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--seen", type=int, default=500)
    parser.add_argument("--paraphrase", type=int, default=500)
    parser.add_argument("--valid", type=int, default=60)
    parser.add_argument("--exclude-keys", default="",
                        help="comma-separated event keys to hold out entirely (ablation); "
                             f"'ablation' means {','.join(ABLATION_KEYS)}")
    args = parser.parse_args(argv)
    exclude = ABLATION_KEYS if args.exclude_keys == "ablation" else \
        tuple(k for k in args.exclude_keys.split(",") if k)
    unknown = set(exclude) - set(HELDOUT)
    if unknown:
        parser.error(f"unknown event keys: {sorted(unknown)}")
    manifest = build(args.out, args.seen, args.paraphrase, args.valid, exclude)
    counts = {name: len(rows) for name, rows in manifest["files"].items()}
    print(f"wrote {counts} to {args.out} (exclude_keys={list(exclude)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
