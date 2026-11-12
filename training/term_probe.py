"""Probe: how often do a model's terms find the cause when it is asked for terms only?

    $MLX_PY training/term_probe.py --model <hf-model> [--adapter DIR] --claims-from <cached proposer name> \
        --suite dev --phrasings heldout [--samples 4 --temp 0.8]

Claims (quote, account, figures, reason) are taken from a cached proposer; only the search
terms are replaced by what `--model` answers to the teacher's prompt (`teacher_terms.BRIEF`:
account names and the stated reason, nothing from the ledger). The checker then says how
many true claims had their cause found (`hit_rate.outcomes`). With `--samples K` the terms of
K sampled answers are pooled, most-proposed first, and both the capped (8) and uncapped
pools are scored: the uncapped one is a ceiling on what better ranking could reach.
A measuring tool for choosing a base model, not a proposer: dev worlds only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import replace
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

from mlx_lm import load  # noqa: E402
from mlx_lm.sample_utils import make_sampler  # noqa: E402

import memguard  # noqa: E402
from batch_propose import generate  # noqa: E402
from hit_rate import outcomes  # noqa: E402
from teacher_terms import BRIEF, SYSTEM  # noqa: E402
from proven import netguard, worlds  # noqa: E402
from proven.budget import Budget  # noqa: E402
from proven.extractors import build  # noqa: E402
from proven.llm import restates_account  # noqa: E402
from proven.synth import generate_split  # noqa: E402


class Swapped:
    """A cached proposer's claims with other search terms."""
    name, version = "probe", "0.1"

    def __init__(self, inner, terms: dict, cap: int | None):
        self.inner, self.terms, self.cap = inner, terms, cap

    def propose(self, text, ledger):
        out = []
        for p in self.inner.propose(text, ledger):
            mine = [t for t in self.terms.get((p.account, p.driver_text), [])
                    if not restates_account(t, p.account or "", ledger)]
            out.append(replace(p, driver_terms=tuple(mine[:self.cap] if self.cap else mine)))
        return out


def parse(text: str) -> list[str]:
    try:
        start, end = text.find("{"), text.rfind("}")
        data = json.loads(text[start:end + 1])
        items = next(iter(data.values())) if isinstance(data, dict) else data
    except (ValueError, StopIteration):
        items = re.findall(r'"([^"]+)"', text)
    return [re.sub(r"\s+", " ", str(t)).strip().lower() for t in items if str(t).strip()][:12]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model", required=True)
    p.add_argument("--adapter", default="")
    p.add_argument("--claims-from", required=True)
    p.add_argument("--suite", default="dev")
    p.add_argument("--phrasings", nargs="+", default=["heldout"])
    p.add_argument("--samples", type=int, default=1)
    p.add_argument("--temp", type=float, default=0.8)
    p.add_argument("--batch", type=int, default=16)
    args = p.parse_args(argv)
    if args.suite != "dev":
        p.error("the probe is for the dev worlds")
    memguard.install()
    netguard.install()
    inner = build("openweight", model=args.claims_from, budget=Budget(None, 1.0))
    asks: dict[tuple, str] = {}
    for world in worlds.suite(args.suite):
        chart = "\n".join(f"- {spec.name}" for spec in world.specs)
        for phrasing in args.phrasings:
            split = generate_split("test", 100, phrasing, world=world)
            for scenario in split[:len(split) // 2]:
                for prop in inner.propose(scenario.explanation, scenario.ledger):
                    if prop.driver_text and prop.account:
                        asks[(prop.account, prop.driver_text)] = BRIEF.format(
                            chart=chart, items=f'1. [{prop.account}] "{prop.driver_text}"')
    model, tokenizer = load(args.model, adapter_path=args.adapter or None)
    model.eval()
    keys = list(asks)
    prompts = [tokenizer.apply_chat_template(
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": asks[k]}],
        add_generation_prompt=True, tokenize=True) for k in keys]
    pools: dict[tuple, dict[str, int]] = {k: {} for k in keys}
    first: dict[tuple, list[str]] = {}
    for round_ in range(args.samples):
        sampler = make_sampler(temp=args.temp) if round_ else None
        for i in range(0, len(keys), args.batch):
            texts = generate(model, tokenizer, prompts[i:i + args.batch], 160, None, sampler)
            for key, text in zip(keys[i:i + args.batch], texts):
                terms = parse(text)
                if not round_:
                    first[key] = terms
                for t in dict.fromkeys(terms):
                    pools[key][t] = pools[key].get(t, 0) + 1
        print(f"round {round_ + 1}/{args.samples} done", flush=True)
    voted = {k: [t for t, _ in sorted(v.items(), key=lambda kv: -kv[1])] for k, v in pools.items()}
    print(f"{len(keys)} distinct (account, reason) pairs; e.g. {keys[0]} -> {first[keys[0]]}")
    for label, terms, cap in (("greedy, 8 terms", first, 8), (f"vote of {args.samples}, 8 terms", voted, 8),
                              (f"pool of {args.samples}, uncapped", voted, None)):
        for phrasing in args.phrasings:
            o = outcomes(Swapped(inner, terms, cap), args.suite, phrasing)
            print(f"{label:26s} {phrasing:10s} found {o['found'] / o['claims']:.1%} of {o['claims']} "
                  f"(routine {o['routine']}, nothing {o['nothing']}, other {o['other']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
