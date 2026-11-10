"""Answer every close of a world suite with a local MLX proposer, in batches, into the cache.

    $MLX_PY training/batch_propose.py --model mlx-community/Qwen2.5-3B-Instruct-4bit \
        --adapter <adapter-dir> --name proven-qwen3b-worlds --suite unseen --n 100

`mlx_lm.server` answers one request at a time, which makes a 2,200-close suite a two-hour
job. This script generates the replies with `mlx_lm.batch_generate` instead (greedy, the
chat template applied to the same system and user messages `proven.openweight` sends) and
then runs each close through the real `OpenWeightExtractor` and `CachedExtractor`, with a
transport that hands back the pre-generated reply. Parsing, admission and the cache key are
therefore the harness's own, and a later

    python -m proven teach-sim --extractor openweight --model <name> --worlds <suite>

is answered from the cache. `--suite default` covers the default world's test split instead.
The raw replies are also written to `--replies` (JSON lines), so a run can be re-scored.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

from mlx_lm import load  # noqa: E402
from mlx_lm.generate import batch_generate  # noqa: E402

import memguard  # noqa: E402
from proven import worlds  # noqa: E402
from proven.cache import CachedExtractor  # noqa: E402
from proven.llm import SYSTEM, payload  # noqa: E402
from proven.openweight import OpenWeightExtractor  # noqa: E402
from proven.synth import generate_split  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model", required=True)
    p.add_argument("--adapter", default="")
    p.add_argument("--name", required=True, help="the model name the cache is keyed by")
    p.add_argument("--suite", default="unseen")
    p.add_argument("--phrasings", nargs="+", default=["heldout", "paraphrase"])
    p.add_argument("--n", type=int, default=100)
    p.add_argument("--batch", type=int, default=12)
    p.add_argument("--max-tokens", type=int, default=1200)
    p.add_argument("--limit", type=int, default=0, help="only the first N closes (timing runs)")
    p.add_argument("--replies", type=Path, default=None)
    p.add_argument("--cache-dir", default=os.environ.get("PROVEN_CACHE_DIR") or ".proven/cache")
    args = p.parse_args(argv)

    memguard.install()
    if args.suite == "default":
        closes = [s for ph in args.phrasings for s in generate_split("test", args.n, ph)]
    else:
        closes = [s for world in worlds.suite(args.suite) for ph in args.phrasings
                  for s in generate_split("test", args.n, ph, world=world)]
    if args.limit:
        closes = closes[:args.limit]
    replies: dict[str, str] = {}

    def transport(url: str, headers: dict, body: bytes) -> bytes:
        content = json.loads(body)["messages"][1]["content"]
        return json.dumps({"choices": [{"message": {"content": replies[content]},
                                        "finish_reason": "stop"}]}).encode("utf-8")

    extractor = CachedExtractor(OpenWeightExtractor(transport=transport, model=args.name,
                                                    base_url="http://127.0.0.1:8090/v1"), args.cache_dir)
    todo = [s for s in closes if extractor.key(s.explanation, s.ledger) not in extractor._memory]
    print(f"{len(closes)} closes, {len(closes) - len(todo)} already cached", flush=True)
    if not todo:
        return 0
    model, tokenizer = load(args.model, adapter_path=args.adapter or None)
    model.eval()
    todo.sort(key=lambda s: len(s.explanation))          # similar lengths batch well
    out = args.replies.open("a", encoding="utf-8") if args.replies else None
    start, empty = time.time(), 0
    for i in range(0, len(todo), args.batch):
        part = todo[i:i + args.batch]
        contents = [payload(s.explanation, s.ledger) for s in part]
        prompts = [tokenizer.apply_chat_template(
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": c}],
            add_generation_prompt=True, tokenize=True) for c in contents]
        texts = batch_generate(model, tokenizer, prompts, max_tokens=args.max_tokens).texts
        for scenario, content, text in zip(part, contents, texts):
            replies[content] = text
            proposals = extractor.propose(scenario.explanation, scenario.ledger)
            empty += not proposals
            if out:
                out.write(json.dumps({"id": scenario.scenario_id, "reply": text}) + "\n")
        done = i + len(part)
        if (i // args.batch) % 10 == 0 or done == len(todo):
            rate = (time.time() - start) / done
            print(f"{done}/{len(todo)} closes, {rate:.2f}s each, {empty} with no proposals", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
